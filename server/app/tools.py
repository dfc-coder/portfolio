from __future__ import annotations

import datetime as dt
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .portfolio import Portfolio

_WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
_OFFSET_UNITS = ("minutes", "hours", "days", "weeks")

SEARCH_PORTFOLIO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_portfolio",
        "description": (
            "Look up factual professional information about Diego Cano. Use it only when the visitor explicitly "
            "asks about Diego, his experience, skills, projects, education, certifications, services, or "
            "professional background, or when the message is an unambiguous follow-up to a previous question "
            "about Diego. Do not use it for greetings, thanks, jokes, definitions, general programming questions, "
            "creative requests, or general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Short query for the exact professional fact that needs to be retrieved.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

RESOLVE_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "resolve_datetime",
        "description": (
            "Deterministically resolve current, relative, or explicit date and time questions, including weekday "
            "questions. This tool is read-only and never creates reminders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Temporal anchor. Use the literal value 'now' when the request does not contain an explicit "
                        "date or time. If the request contains an explicit date or time, normalize it to ISO-8601 "
                        "and place it here. Use YYYY-MM-DD for a date without a time."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Relative amount applied to `reference`. Examples: 'tomorrow' => offset=1 and unit='days'; "
                        "'yesterday' => offset=-1 and unit='days'; 'in one week' => offset=1 and unit='weeks'; "
                        "'in 2 hours' => offset=2 and unit='hours'. Use offset=0 only when the question is about "
                        "the reference itself."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": (
                        "Unit for `offset`: 'minutes', 'hours', 'days', or 'weeks'."
                    ),
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit it to use the server timezone.",
                },
            },
            "required": ["reference", "offset", "unit"],
            "additionalProperties": False,
        },
    },
}

SET_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_reminder_mock",
        "description": (
            "Create a simulated, non-persistent reminder. Use it whenever the visitor asks to create a reminder, "
            "with either a relative or absolute schedule. The tool resolves its own temporal reference, so there "
            "is no need to call `resolve_datetime` first. It does not schedule or send a real notification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Temporal anchor for the reminder. Use the literal value 'now' for a relative reminder. "
                        "If the request contains an explicit date or time, normalize it to ISO-8601 and place it here."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Relative amount applied to `reference`. Examples: 'in 30 minutes' => offset=30 and "
                        "unit='minutes'; 'in 2 hours' => offset=2 and unit='hours'; 'in 7 days' => offset=7 and "
                        "unit='days'. Use offset=0 for an explicit absolute date or time."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": (
                        "Unit for `offset`: 'minutes', 'hours', 'days', or 'weeks'."
                    ),
                },
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text without scheduling instructions.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit it to use the server timezone.",
                },
            },
            "required": ["reference", "offset", "unit", "message"],
            "additionalProperties": False,
        },
    },
}


async def search_portfolio(portfolio: Portfolio, query: str) -> dict[str, object]:
    return {"facts": await portfolio.search(query)}


def resolve_datetime(
    reference: str,
    offset: int,
    unit: str,
    timezone: str | None = None,
) -> dict[str, object]:
    value, zone_name = _resolve_reference(reference, timezone)
    return _datetime_result(value + _offset_delta(offset, unit), zone_name)


def set_reminder_mock(
    reference: str,
    offset: int,
    unit: str,
    message: str,
    timezone: str | None = None,
) -> dict[str, object]:
    value, _ = _resolve_reference(reference, timezone)
    return _reminder_result(value + _offset_delta(offset, unit), message)


ToolHandler = Callable[[dict[str, Any], Portfolio], Awaitable[object]]


@dataclass(frozen=True)
class Tool:
    schema: dict[str, Any]
    run: ToolHandler

    @property
    def name(self) -> str:
        return str(self.schema["function"]["name"])


async def _run_search_portfolio(payload: dict[str, Any], portfolio: Portfolio) -> object:
    _only(payload, {"query"})
    return await search_portfolio(
        portfolio,
        _required_string(payload, "query", max_length=500),
    )


async def _run_resolve_datetime(payload: dict[str, Any], portfolio: Portfolio) -> object:
    del portfolio
    _only(payload, {"reference", "offset", "unit", "timezone"})
    return resolve_datetime(
        reference=_required_string(payload, "reference", max_length=100),
        offset=_required_integer(
            payload,
            "offset",
            minimum=-52560000,
            maximum=52560000,
        ),
        unit=_required_choice(payload, "unit", _OFFSET_UNITS),
        timezone=_optional_timezone(payload),
    )


async def _run_set_reminder_mock(payload: dict[str, Any], portfolio: Portfolio) -> object:
    del portfolio
    _only(payload, {"reference", "offset", "unit", "message", "timezone"})
    return set_reminder_mock(
        reference=_required_string(payload, "reference", max_length=100),
        offset=_required_integer(
            payload,
            "offset",
            minimum=-52560000,
            maximum=52560000,
        ),
        unit=_required_choice(payload, "unit", _OFFSET_UNITS),
        message=_required_string(payload, "message", max_length=500),
        timezone=_optional_timezone(payload),
    )


_REGISTERED_TOOLS = (
    Tool(SEARCH_PORTFOLIO_SCHEMA, _run_search_portfolio),
    Tool(RESOLVE_DATETIME_SCHEMA, _run_resolve_datetime),
    Tool(SET_REMINDER_MOCK_SCHEMA, _run_set_reminder_mock),
)

_TOOL_BY_NAME = {tool.name: tool for tool in _REGISTERED_TOOLS}
if len(_TOOL_BY_NAME) != len(_REGISTERED_TOOLS):
    raise RuntimeError("duplicate tool name")

# Stable model-facing schema list. The registry above is the execution source of truth.
TOOLS = [tool.schema for tool in _REGISTERED_TOOLS]


def tool_name(schema: dict[str, Any]) -> str:
    return str(schema["function"]["name"])


async def run_tool_call(
    call_id: str,
    name: str,
    raw_arguments: str,
    portfolio: Portfolio,
) -> dict[str, str]:
    try:
        payload = json.loads(raw_arguments or "{}")
        if not isinstance(payload, dict):
            raise ValueError("tool arguments must be a JSON object")

        tool = _TOOL_BY_NAME.get(name)
        if tool is None:
            raise ValueError(f"unknown tool: {name}")

        result = await tool.run(payload, portfolio)
        body: dict[str, object] = {"ok": True, "result": result}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        body = {
            "ok": False,
            "error": {"type": "validation_error", "message": str(exc)},
        }
    except Exception as exc:
        body = {
            "ok": False,
            "error": {"type": "tool_error", "message": str(exc)},
        }

    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(body, ensure_ascii=False),
    }


def _resolve_reference(reference: str, timezone: str | None) -> tuple[dt.datetime, str]:
    zone_name = timezone or _default_timezone()
    if reference == "now":
        zone = _zone(zone_name)
        return dt.datetime.now(zone), zone.key

    value = _parse_datetime(reference, zone_name)
    return value, _timezone_name(value, zone_name)


def _offset_delta(offset: int, unit: str) -> dt.timedelta:
    if unit == "minutes":
        return dt.timedelta(minutes=offset)
    if unit == "hours":
        return dt.timedelta(hours=offset)
    if unit == "days":
        return dt.timedelta(days=offset)
    if unit == "weeks":
        return dt.timedelta(weeks=offset)
    raise ValueError(f"unit must be one of: {', '.join(_OFFSET_UNITS)}")


def _optional_timezone(payload: dict[str, Any]) -> str | None:
    timezone = payload.get("timezone")
    if timezone is None:
        return None
    if not isinstance(timezone, str) or not timezone.strip():
        raise ValueError("timezone must be a non-empty string")
    return timezone


def _only(payload: dict[str, Any], allowed: set[str]) -> None:
    extra = set(payload) - allowed
    if extra:
        raise ValueError(f"unexpected tool argument: {sorted(extra)[0]}")


def _required_choice(
    payload: dict[str, Any],
    name: str,
    allowed: tuple[str, ...],
) -> str:
    value = payload.get(name)
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return str(value)


def _required_string(
    payload: dict[str, Any],
    name: str,
    *,
    max_length: int | None = None,
) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{name} must be at most {max_length} characters")
    return value


def _required_integer(
    payload: dict[str, Any],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if name not in payload:
        raise ValueError(f"{name} is required")
    value = payload[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _reminder_result(value: dt.datetime, message: str) -> dict[str, object]:
    return {
        "reminder_id": f"mock-{uuid4()}",
        "datetime": value.isoformat(timespec="seconds"),
        "message": message,
        "status": "simulated_only",
        "persisted": False,
        "will_notify": False,
    }


def _datetime_result(value: dt.datetime, timezone: str) -> dict[str, object]:
    return {
        "datetime": value.isoformat(timespec="seconds"),
        "date": value.date().isoformat(),
        "weekday": value.strftime("%A"),
        "weekday_es": _WEEKDAYS_ES[value.weekday()],
        "iso_weekday": value.isoweekday(),
        "timezone": timezone,
    }


def _timezone_name(value: dt.datetime, fallback: str) -> str:
    return getattr(value.tzinfo, "key", None) or value.tzname() or fallback


def _parse_datetime(value: str, timezone: str) -> dt.datetime:
    zone = _zone(timezone)
    try:
        if len(value) == 10:
            return dt.datetime.combine(dt.date.fromisoformat(value), dt.time.min, zone)
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("reference must be 'now' or valid ISO-8601") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=zone)
    return parsed


def _default_timezone() -> str:
    return os.getenv("TZ", _DEFAULT_TIMEZONE)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc
