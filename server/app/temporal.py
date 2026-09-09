from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from .dispatcher import Route
from .prompt import DATETIME_PROMPT, REMINDER_PROMPT
from .tools import resolve_datetime, set_reminder_mock
from .trace import elapsed_ms, utc_now
from .worker import WorkerResult

_ALLOWED_KINDS = ("date", "weekday", "datetime")
_ALLOWED_UNITS = ("minutes", "hours", "days", "weeks")
_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@dataclass(frozen=True)
class DateTimeRequest:
    kind: str
    reference: str
    offset: int
    unit: str
    timezone: str | None
    language: str


@dataclass(frozen=True)
class ReminderRequest:
    reference: str
    offset: int
    unit: str
    message: str
    timezone: str | None
    language: str


async def run_datetime_fast_path(
    chat: AsyncOpenAI,
    *,
    model: str,
    message: str,
    context: list[dict[str, Any]],
    temperature: float,
    top_p: float,
    top_k: int,
    min_p: float,
    presence_penalty: float,
    repeat_penalty: float,
    max_tokens: int,
    diagnostics: bool,
) -> WorkerResult:
    started = time.perf_counter()
    started_at = utc_now()
    messages = _messages(DATETIME_PROMPT, context, message)
    response = await _structured_completion(
        chat,
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        presence_penalty=presence_penalty,
        repeat_penalty=repeat_penalty,
        max_tokens=max_tokens,
        diagnostics=diagnostics,
    )
    raw = _response_text(response)
    request = _parse_datetime_request(raw)
    arguments = {
        "reference": request.reference,
        "offset": request.offset,
        "unit": request.unit,
    }
    if request.timezone is not None:
        arguments["timezone"] = request.timezone

    operation_started = time.perf_counter()
    operation_started_at = utc_now()
    result = resolve_datetime(**arguments)
    operation_finished_at = utc_now()
    answer = _format_datetime(request, result)

    return WorkerResult(
        route=Route.DATETIME,
        answer=answer,
        protocol_messages=(),
        trace=_trace(
            route=Route.DATETIME,
            model=model,
            message=message,
            context=context,
            messages=messages,
            response=response,
            raw=raw,
            started=started,
            started_at=started_at,
            operation_name="resolve_datetime",
            arguments=arguments,
            result=result,
            operation_started=operation_started,
            operation_started_at=operation_started_at,
            operation_finished_at=operation_finished_at,
            output=answer,
        ),
    )


async def run_reminder_fast_path(
    chat: AsyncOpenAI,
    *,
    model: str,
    message: str,
    context: list[dict[str, Any]],
    temperature: float,
    top_p: float,
    top_k: int,
    min_p: float,
    presence_penalty: float,
    repeat_penalty: float,
    max_tokens: int,
    diagnostics: bool,
) -> WorkerResult:
    started = time.perf_counter()
    started_at = utc_now()
    messages = _messages(REMINDER_PROMPT, context, message)
    response = await _structured_completion(
        chat,
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        presence_penalty=presence_penalty,
        repeat_penalty=repeat_penalty,
        max_tokens=max_tokens,
        diagnostics=diagnostics,
    )
    raw = _response_text(response)
    request = _parse_reminder_request(raw)
    arguments = {
        "reference": request.reference,
        "offset": request.offset,
        "unit": request.unit,
        "message": request.message,
    }
    if request.timezone is not None:
        arguments["timezone"] = request.timezone

    operation_started = time.perf_counter()
    operation_started_at = utc_now()
    result = set_reminder_mock(**arguments)
    operation_finished_at = utc_now()
    answer = _format_reminder(request, result)

    return WorkerResult(
        route=Route.REMINDER,
        answer=answer,
        protocol_messages=(),
        trace=_trace(
            route=Route.REMINDER,
            model=model,
            message=message,
            context=context,
            messages=messages,
            response=response,
            raw=raw,
            started=started,
            started_at=started_at,
            operation_name="set_reminder_mock",
            arguments=arguments,
            result=result,
            operation_started=operation_started,
            operation_started_at=operation_started_at,
            operation_finished_at=operation_finished_at,
            output=answer,
        ),
    )


async def _structured_completion(
    chat: AsyncOpenAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    top_p: float,
    top_k: int,
    min_p: float,
    presence_penalty: float,
    repeat_penalty: float,
    max_tokens: int,
    diagnostics: bool,
) -> Any:
    extra_body: dict[str, object] = {
        "top_k": top_k,
        "min_p": min_p,
        "repeat_penalty": repeat_penalty,
    }
    if diagnostics:
        extra_body.update(
            {
                "verbose": True,
                "timings_per_token": True,
                "return_progress": True,
            }
        )

    return await chat.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        presence_penalty=presence_penalty,
        max_tokens=max_tokens,
        stream=False,
        extra_body=extra_body,
    )


def _messages(
    prompt: str,
    context: list[dict[str, Any]],
    message: str,
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": prompt},
        *_plain_context(context),
        {"role": "user", "content": message},
    ]


def _plain_context(context: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in context[-8:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if content.strip():
            messages.append({"role": role, "content": content})
    return messages


def _response_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("structured worker returned no choices")
    content = getattr(choices[0].message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("structured worker returned an empty response")
    return content.strip()


def _parse_datetime_request(raw: str) -> DateTimeRequest:
    payload = _parse_object(raw)
    _only(payload, {"kind", "reference", "offset", "unit", "timezone", "language"})
    kind = _choice(payload, "kind", _ALLOWED_KINDS)
    reference = _string(payload, "reference", 100)
    offset = _integer(payload, "offset")
    unit = _choice(payload, "unit", _ALLOWED_UNITS)
    timezone = _optional_string(payload, "timezone", 100)
    language = _language(payload)
    return DateTimeRequest(kind, reference, offset, unit, timezone, language)


def _parse_reminder_request(raw: str) -> ReminderRequest:
    payload = _parse_object(raw)
    _only(payload, {"reference", "offset", "unit", "message", "timezone", "language"})
    reference = _string(payload, "reference", 100)
    offset = _integer(payload, "offset")
    unit = _choice(payload, "unit", _ALLOWED_UNITS)
    reminder_message = _string(payload, "message", 500)
    timezone = _optional_string(payload, "timezone", 100)
    language = _language(payload)
    return ReminderRequest(reference, offset, unit, reminder_message, timezone, language)


def _parse_object(raw: str) -> dict[str, Any]:
    value = raw.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()
            if value.startswith("json"):
                value = value[4:].lstrip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("structured worker returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("structured worker response must be a JSON object")
    return payload


def _only(payload: dict[str, Any], allowed: set[str]) -> None:
    extra = set(payload) - allowed
    if extra:
        raise RuntimeError(f"unexpected structured field: {sorted(extra)[0]}")


def _string(payload: dict[str, Any], name: str, maximum: int) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{name} must be a non-empty string")
    if len(value) > maximum:
        raise RuntimeError(f"{name} is too long")
    return value.strip()


def _optional_string(payload: dict[str, Any], name: str, maximum: int) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise RuntimeError(f"{name} must be null or a non-empty string")
    return value.strip()


def _integer(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{name} must be an integer")
    if not -52560000 <= value <= 52560000:
        raise RuntimeError(f"{name} is out of range")
    return value


def _choice(payload: dict[str, Any], name: str, allowed: tuple[str, ...]) -> str:
    value = payload.get(name)
    if value not in allowed:
        raise RuntimeError(f"{name} must be one of: {', '.join(allowed)}")
    return str(value)


def _language(payload: dict[str, Any]) -> str:
    value = payload.get("language")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("language must be a non-empty string")
    return value.strip().lower()


def _format_datetime(request: DateTimeRequest, result: dict[str, object]) -> str:
    value = dt.datetime.fromisoformat(str(result["datetime"]))
    weekday_es = str(result["weekday_es"])
    weekday_en = str(result["weekday"])

    if request.language.startswith("es"):
        date_text = f"{value.day} de {_MONTHS_ES[value.month - 1]} de {value.year}"
        if request.kind == "weekday":
            return f"El {date_text} es {weekday_es}."
        if request.kind == "datetime":
            return f"Fecha y hora: {weekday_es}, {date_text}, {value:%H:%M}."
        return f"Fecha: {weekday_es}, {date_text}."

    date_text = value.strftime("%B %-d, %Y")
    if request.kind == "weekday":
        return f"{date_text} is {weekday_en}."
    if request.kind == "datetime":
        return f"Date and time: {weekday_en}, {date_text}, {value:%H:%M}."
    return f"Date: {weekday_en}, {date_text}."


def _format_reminder(request: ReminderRequest, result: dict[str, object]) -> str:
    value = dt.datetime.fromisoformat(str(result["datetime"]))
    if request.language.startswith("es"):
        date_text = f"{value.day} de {_MONTHS_ES[value.month - 1]} de {value.year} a las {value:%H:%M}"
        return (
            f"Recordatorio simulado creado para el {date_text}: {request.message}. "
            "No es persistente y no enviará una notificación real."
        )
    date_text = value.strftime("%B %-d, %Y at %H:%M")
    return (
        f"Simulated reminder created for {date_text}: {request.message}. "
        "It is not persistent and will not send a real notification."
    )


def _trace(
    *,
    route: Route,
    model: str,
    message: str,
    context: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    response: Any,
    raw: str,
    started: float,
    started_at: str,
    operation_name: str,
    arguments: dict[str, Any],
    result: dict[str, object],
    operation_started: float,
    operation_started_at: str,
    operation_finished_at: str,
    output: str,
) -> dict[str, Any]:
    body = {"ok": True, "result": result}
    operation = {
        "id": f"direct-{uuid4()}",
        "name": operation_name,
        "arguments_raw": json.dumps(arguments, ensure_ascii=False),
        "arguments": arguments,
        "started_at": operation_started_at,
        "finished_at": operation_finished_at,
        "duration_ms": elapsed_ms(operation_started),
        "ok": True,
        "direct": True,
        "result_raw": json.dumps(body, ensure_ascii=False),
        "result": body,
    }
    return {
        "trace_id": str(uuid4()),
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_ms": elapsed_ms(started),
        "status": "ok",
        "input": {"message": message, "context": context},
        "model": {"name": model},
        "generation": {"stream": False, "native_tools": False},
        "tools": [],
        "rounds": [
            {
                "round": 1,
                "request_messages": messages,
                "response": _response_metadata(response, raw),
                "assistant_message": {"role": "assistant", "content": raw},
                "tool_calls": [operation],
            }
        ],
        "output": output,
        "returned_context": [],
        "error": None,
        "route": route.value,
    }


def _response_metadata(response: Any, raw: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"content": raw}
    dump = getattr(response, "model_dump", None)
    if callable(dump):
        data = dump(exclude_none=True)
        for key in (
            "id",
            "object",
            "model",
            "created",
            "system_fingerprint",
            "usage",
            "timings",
        ):
            if key in data:
                payload[key] = data[key]

    choices = getattr(response, "choices", None) or []
    if choices:
        finish_reason = getattr(choices[0], "finish_reason", None)
        if finish_reason is not None:
            payload["finish_reason"] = finish_reason
    return payload
