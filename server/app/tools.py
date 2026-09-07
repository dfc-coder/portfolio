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
_BASES = ("now", "provided")

SEARCH_PORTFOLIO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_portfolio",
        "description": (
            "Search the professional portfolio and CV for factual evidence about experience, skills, "
            "projects, education, certifications, services, or background. Returns relevant passages "
            "with source identifiers. An empty result means the available portfolio does not confirm the fact."
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
            "Read-only date and time resolver. Use it for current, relative, or supplied calendar "
            "date/time questions, including weekday questions. It returns deterministic date/time values "
            "and never creates reminders or performs another action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "enum": list(_BASES),
                    "description": (
                        "Use now when the request is anchored to the current moment, including today, "
                        "tomorrow, yesterday, or a duration from now. Use provided only when the request "
                        "contains an explicit ISO-8601 date or datetime."
                    ),
                },
                "datetime": {
                    "type": "string",
                    "description": (
                        "ISO-8601 date or datetime copied from the request. Required when base is provided; "
                        "omit when base is now."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": "Signed quantity applied to the base. Use 0 when no shift is requested.",
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
            "required": ["base", "offset", "unit"],
            "additionalProperties": False,
        },
    },
}

SET_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_reminder_mock",
        "description": (
            "Create a simulated, non-persistent reminder at an absolute ISO-8601 datetime. "
            "No real notification is scheduled or sent. For a relative reminder, first call "
            "resolve_datetime to obtain the absolute target datetime, then call this function with that result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "Absolute ISO-8601 reminder datetime copied from the request or from a prior "
                        "resolve_datetime result. Do not invent an absolute datetime from relative language."
                    ),
                },
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text without scheduling instructions.",
                },
            },
            "required": ["datetime", "message"],
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
    base: str,
    offset: int,
    unit: str,
    datetime: str | None = None,
    timezone: str | None = None,
) -> dict[str, object]:
    zone_name = timezone or _default_timezone()

    if base == "now":
        if datetime is not None:
            raise ValueError("datetime must be omitted when base is now")
        zone = _zone(zone_name)
        value = dt.datetime.now(zone)
        result_timezone = zone.key
    elif base == "provided":
        if datetime is None:
            raise ValueError("datetime is required when base is provided")
        value = _parse_datetime(datetime, zone_name)
        result_timezone = _timezone_name(value, zone_name)
    else:
        raise ValueError(f"base must be one of: {', '.join(_BASES)}")

    shifted = value + _offset_delta(offset, unit)
    return _datetime_result(shifted, result_timezone)


def set_reminder_mock(datetime: str, message: str) -> dict[str, object]:
    return _reminder_result(_aware_datetime(datetime), message)


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
        _only(payload, {"base", "datetime", "offset", "unit", "timezone"})
        return resolve_datetime(
            base=_required_choice(payload, "base", _BASES),
            datetime=_optional_string(payload, "datetime"),
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
        _only(payload, {"datetime", "message"})
        return set_reminder_mock(
            _required_string(payload, "datetime"),
            _required_string(payload, "message", max_length=500),
        )

    raise ValueError(f"unknown tool: {name}")


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


def _optional_string(payload: dict[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


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
        raise ValueError("datetime must be valid ISO-8601") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=zone)
    return parsed


def _aware_datetime(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("datetime must be valid ISO-8601") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return parsed


def _default_timezone() -> str:
    return os.getenv("TZ", _DEFAULT_TIMEZONE)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc
