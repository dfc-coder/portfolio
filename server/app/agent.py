from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from .portfolio import Portfolio
from .prompt import build_messages
from .tools import TOOL_SCHEMAS, execute_tool

MAX_CONTEXT_MESSAGES = 32
MAX_TOOL_ROUNDS = 4
AgentEvent = tuple[str, dict[str, object]]


class Agent:
    def __init__(
        self,
        subject: str,
        chat: AsyncOpenAI,
        portfolio: Portfolio,
        *,
        model: str,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 1,
        min_p: float = 0.0,
        presence_penalty: float = 0.0,
        repeat_penalty: float = 1.0,
        max_tokens: int = 256,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._portfolio = portfolio
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._min_p = min_p
        self._presence_penalty = presence_penalty
        self._repeat_penalty = repeat_penalty
        self._max_tokens = max_tokens

    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        history = _trim_context(context)
        conversation = [*history, {"role": "user", "content": message}]
        messages = build_messages(self._subject, history, message)
        trace = _new_trace(message, context, self._model) if diagnostics else None

        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 2):
                yield "status", {"phase": "model", "round": round_number}
                round_started = time.perf_counter()
                round_trace = _start_round(trace, round_number)

                stream = await self._chat.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=list(TOOL_SCHEMAS),
                    parallel_tool_calls=False,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    presence_penalty=self._presence_penalty,
                    max_tokens=self._max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                    extra_body={
                        "top_k": self._top_k,
                        "min_p": self._min_p,
                        "repeat_penalty": self._repeat_penalty,
                    },
                )

                mode: str | None = None
                pending_text: list[str] = []
                answer_parts: list[str] = []
                calls: dict[int, dict[str, str]] = {}
                finish_reason: str | None = None

                async for chunk in stream:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue

                    choice = choices[0]
                    if getattr(choice, "finish_reason", None) is not None:
                        finish_reason = choice.finish_reason

                    delta = choice.delta
                    tool_deltas = getattr(delta, "tool_calls", None) or []
                    text = getattr(delta, "content", None) or ""

                    if tool_deltas:
                        if mode == "final":
                            raise RuntimeError("model mixed final text with tool calls")
                        mode = "tool"
                        pending_text.clear()
                        _merge_tool_calls(calls, tool_deltas)

                    if not text:
                        continue

                    if mode == "tool":
                        if text.strip():
                            raise RuntimeError("model mixed final text with tool calls")
                        continue

                    if mode is None:
                        pending_text.append(text)
                        buffered = "".join(pending_text)
                        if not buffered.strip():
                            continue
                        mode = "final"
                        pending_text.clear()
                        answer_parts.append(buffered)
                        yield "status", {"phase": "responding", "round": round_number}
                        yield "token", {"text": buffered}
                        continue

                    answer_parts.append(text)
                    yield "token", {"text": text}

                _finish_round(round_trace, finish_reason, round_started)

                if mode == "final":
                    answer = "".join(answer_parts).strip()
                    if not answer:
                        raise RuntimeError("model returned an empty answer")

                    conversation.append({"role": "assistant", "content": answer})
                    returned_context = _trim_context(conversation)
                    yield "context", {"messages": returned_context}
                    if trace is not None:
                        yield "trace", _finish_trace(trace, answer, returned_context, None)
                    return

                if mode != "tool" or not calls:
                    raise RuntimeError("model returned no answer and no tool call")
                if round_number > MAX_TOOL_ROUNDS:
                    raise RuntimeError("tool loop limit reached")

                ordered_calls = _ordered_calls(calls)
                assistant_message = _assistant_tool_message(ordered_calls)
                messages.append(assistant_message)
                conversation.append(assistant_message)

                for call in ordered_calls:
                    yield "tool", {
                        "name": call["name"],
                        "state": "running",
                        "round": round_number,
                    }
                    tool_started = time.perf_counter()
                    result = await execute_tool(
                        call["name"],
                        call["arguments"],
                        self._portfolio,
                    )
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                    messages.append(tool_message)
                    conversation.append(tool_message)
                    _record_tool(round_trace, call, result, tool_started)
                    yield "tool", {
                        "name": call["name"],
                        "state": "done",
                        "ok": bool(result.get("ok")),
                        "round": round_number,
                    }

            raise RuntimeError("tool loop limit reached")
        except Exception as exc:
            if trace is not None:
                yield "trace", _finish_trace(
                    trace,
                    None,
                    None,
                    {"type": type(exc).__name__, "message": str(exc)},
                )
            raise


def _merge_tool_calls(calls: dict[int, dict[str, str]], deltas: list[Any]) -> None:
    for delta in deltas:
        item = calls.setdefault(delta.index, {"id": "", "name": "", "arguments": ""})
        if getattr(delta, "id", None):
            item["id"] += delta.id
        function = getattr(delta, "function", None)
        if function is None:
            continue
        if getattr(function, "name", None):
            item["name"] += function.name
        if getattr(function, "arguments", None):
            item["arguments"] += function.arguments


def _ordered_calls(calls: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    ordered = [calls[index] for index in sorted(calls)]
    for call in ordered:
        if not call["id"] or not call["name"]:
            raise RuntimeError("model returned an incomplete tool call")
    return ordered


def _assistant_tool_message(calls: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in calls
        ],
    }


def _trim_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(messages) <= MAX_CONTEXT_MESSAGES:
        return messages

    start = len(messages) - MAX_CONTEXT_MESSAGES
    while start < len(messages) and messages[start].get("role") != "user":
        start += 1
    return messages[start:]


def _new_trace(message: str, context: list[dict[str, Any]], model: str) -> dict[str, Any]:
    return {
        "trace_id": str(uuid4()),
        "started_at": _utc_now(),
        "_started": time.perf_counter(),
        "status": "running",
        "input": {"message": message, "context": context},
        "model": {"name": model},
        "rounds": [],
        "output": None,
        "returned_context": None,
        "error": None,
    }


def _start_round(trace: dict[str, Any] | None, number: int) -> dict[str, Any] | None:
    if trace is None:
        return None
    value = {
        "round": number,
        "response": {"finish_reason": None, "duration_ms": None},
        "tool_calls": [],
    }
    trace["rounds"].append(value)
    return value


def _finish_round(
    round_trace: dict[str, Any] | None,
    finish_reason: str | None,
    started: float,
) -> None:
    if round_trace is None:
        return
    round_trace["response"]["finish_reason"] = finish_reason
    round_trace["response"]["duration_ms"] = _elapsed_ms(started)


def _record_tool(
    round_trace: dict[str, Any] | None,
    call: dict[str, str],
    result: dict[str, object],
    started: float,
) -> None:
    if round_trace is None:
        return
    round_trace["tool_calls"].append(
        {
            "id": call["id"],
            "name": call["name"],
            "arguments_raw": call["arguments"],
            "arguments": _parse_json(call["arguments"]),
            "duration_ms": _elapsed_ms(started),
            "ok": bool(result.get("ok")),
            "result": result,
        }
    )


def _finish_trace(
    trace: dict[str, Any],
    output: str | None,
    returned_context: list[dict[str, Any]] | None,
    error: dict[str, str] | None,
) -> dict[str, Any]:
    trace["status"] = "error" if error else "ok"
    trace["output"] = output
    trace["returned_context"] = returned_context
    trace["error"] = error
    trace["finished_at"] = _utc_now()
    trace["duration_ms"] = _elapsed_ms(trace.pop("_started"))
    return trace


def _parse_json(value: str) -> object | None:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
