from __future__ import annotations

import datetime as dt
import json
import os
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
            "Search the professional portfolio and CV for factual evidence specifically about the portfolio "
            "subject's experience, skills, projects, education, certifications, services, or background. "
            "Use it only for factual questions about the portfolio subject. Do not use it for general "
            "conversation, jokes, creative requests, definitions, or general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Concise search query for the exact professional fact needed.",
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
            "Read-only date and time resolver for current, relative, or explicitly supplied calendar "
            "date/time questions, including weekday questions. It never creates reminders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Temporal anchor. Use the literal value 'now' only when the request contains no "
                        "explicit calendar date or datetime. When the request contains an explicit calendar "
                        "date or datetime, normalize that value to ISO-8601 and put it here. For a date-only "
                        "request use YYYY-MM-DD. Never replace an explicit date with an offset from now."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Signed quantity applied to reference. Preserve the requested duration; use 0 when "
                        "the request asks only about the reference itself."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Offset unit: minutes, hours, days, or weeks.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
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
            "Create a simulated, non-persistent reminder. Use this action for every request that asks to "
            "create a reminder, whether its schedule is relative or absolute. It resolves its own temporal "
            "reference; a separate read-only date-resolution call is unnecessary. No real notification is "
            "scheduled or sent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Reminder time anchor. Use the literal value 'now' for a relative reminder. When the "
                        "request supplies an explicit calendar date or datetime, normalize it to ISO-8601 "
                        "and put it here."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Signed quantity applied to reference. Preserve the requested duration; use 0 for "
                        "an explicit absolute reminder time."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Offset unit: minutes, hours, days, or weeks.",
                },
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text without scheduling instructions.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
                },
            },
            "required": ["reference", "offset", "unit", "message"],
            "additionalProperties": False,
        },
    },
}

TOOLS = [
    SEARCH_PORTFOLIO_SCHEMA,
    RESOLVE_DATETIME_SCHEMA,
    SET_REMINDER_MOCK_SCHEMA,
]


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
        result = await _run_tool(name, payload, portfolio)
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


async def _run_tool(
    name: str,
    payload: dict[str, Any],
    portfolio: Portfolio,
) -> object:
    if name == "search_portfolio":
        _only(payload, {"query"})
        return await search_portfolio(
            portfolio,
            _required_string(payload, "query", max_length=500),
        )

    if name == "resolve_datetime":
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

    if name == "set_reminder_mock":
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

    raise ValueError(f"unknown tool: {name}")


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
