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

GET_CURRENT_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_datetime",
        "description": (
            "Return the actual current date and time. Use only for requests about now or today with no "
            "temporal offset. For tomorrow, yesterday, next week, or any offset from now, use "
            "get_relative_datetime."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone such as America/Argentina/Buenos_Aires. "
                        "Omit to use the server timezone."
                    ),
                }
            },
            "additionalProperties": False,
        },
    },
}

GET_RELATIVE_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_relative_datetime",
        "description": (
            "Resolve a date or time at a non-zero offset from the actual current moment. Preferred for "
            "tomorrow, yesterday, next week, in N days or hours, N days or hours ago, and the weekday of "
            "a relative date. Requires at least one non-zero days, hours, or minutes value. If the request "
            "supplies an explicit base date or datetime, use shift_datetime instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole-day offset from now.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole-hour offset from now.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole-minute offset from now.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
                },
            },
            "additionalProperties": False,
        },
    },
}

SHIFT_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "shift_datetime",
        "description": (
            "Shift an explicit date or datetime by a non-zero duration. Preferred only when the request "
            "contains both a concrete base date or datetime and arithmetic such as '5 days after 2026-12-25'. "
            "Requires datetime plus at least one non-zero days, hours, or minutes value. For offsets from the "
            "actual current moment, use get_relative_datetime."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "Explicit ISO-8601 base date or datetime, for example 2026-12-25 or "
                        "2026-09-07T12:30:00-03:00."
                    ),
                },
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole-day offset from the explicit base.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole-hour offset from the explicit base.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole-minute offset from the explicit base.",
                },
            },
            "required": ["datetime"],
            "additionalProperties": False,
        },
    },
}

GET_WEEKDAY_FOR_EXPLICIT_DATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weekday_for_explicit_date",
        "description": (
            "Return the weekday for an exact calendar date supplied by the request. Use only when a concrete "
            "YYYY-MM-DD date is present and no date arithmetic is requested. Relative dates such as yesterday "
            "or tomorrow belong to get_relative_datetime."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Explicit ISO-8601 calendar date in YYYY-MM-DD form, for example 2026-12-25.",
                }
            },
            "required": ["date"],
            "additionalProperties": False,
        },
    },
}

SET_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_reminder_mock",
        "description": (
            "Create a simulated, non-persistent reminder at an explicit absolute datetime supplied by the "
            "request. Use only when the request contains the exact ISO-8601 reminder datetime with a timezone "
            "offset. Relative reminders belong to set_relative_reminder_mock."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "Absolute ISO-8601 reminder datetime with timezone offset, "
                        "for example 2026-09-10T15:00:00-03:00."
                    ),
                },
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text.",
                },
            },
            "required": ["datetime", "message"],
            "additionalProperties": False,
        },
    },
}

SET_RELATIVE_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_relative_reminder_mock",
        "description": (
            "Create a simulated, non-persistent reminder at a non-zero offset from the actual current moment. "
            "Preferred for requests such as 'remind me in 30 minutes', 'in 2 hours', or 'in 7 days'. Requires "
            "a message and at least one non-zero days, hours, or minutes value."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text.",
                },
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole-day offset from now.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole-hour offset from now.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole-minute offset from now.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
                },
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
}

TOOLS = [
    SEARCH_PORTFOLIO_SCHEMA,
    GET_CURRENT_DATETIME_SCHEMA,
    GET_RELATIVE_DATETIME_SCHEMA,
    SHIFT_DATETIME_SCHEMA,
    GET_WEEKDAY_FOR_EXPLICIT_DATE_SCHEMA,
    SET_REMINDER_MOCK_SCHEMA,
    SET_RELATIVE_REMINDER_MOCK_SCHEMA,
]


async def search_portfolio(portfolio: Portfolio, query: str) -> dict[str, object]:
    return {"facts": await portfolio.search(query)}


def get_current_datetime(timezone: str | None = None) -> dict[str, object]:
    zone = _zone(timezone or _default_timezone())
    return _datetime_result(dt.datetime.now(zone), zone.key)


def get_relative_datetime(
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    timezone: str | None = None,
) -> dict[str, object]:
    _require_offset(days, hours, minutes)
    value, zone_name = _datetime_from_now(days, hours, minutes, timezone)
    return _datetime_result(value, zone_name)


def shift_datetime(
    datetime: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    *,
    default_timezone: str | None = None,
) -> dict[str, object]:
    _require_offset(days, hours, minutes)
    timezone = default_timezone or _default_timezone()
    value = _parse_datetime(datetime, timezone)
    shifted = value + dt.timedelta(days=days, hours=hours, minutes=minutes)
    return _datetime_result(shifted, _timezone_name(shifted, timezone))


def get_weekday_for_explicit_date(
    date: str,
    *,
    default_timezone: str | None = None,
) -> dict[str, object]:
    zone = _zone(default_timezone or _default_timezone())
    try:
        value = dt.datetime.combine(dt.date.fromisoformat(date), dt.time.min, zone)
    except ValueError as exc:
        raise ValueError("date must be valid ISO-8601 YYYY-MM-DD") from exc
    return _datetime_result(value, zone.key)


def set_reminder_mock(datetime: str, message: str) -> dict[str, object]:
    return _reminder_result(_aware_datetime(datetime), message)


def set_relative_reminder_mock(
    message: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    timezone: str | None = None,
) -> dict[str, object]:
    _require_offset(days, hours, minutes)
    value, _ = _datetime_from_now(days, hours, minutes, timezone)
    return _reminder_result(value, message)


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
        query = _required_string(payload, "query", max_length=500)
        return await search_portfolio(portfolio, query)

    if name == "get_current_datetime":
        _only(payload, {"timezone"})
        return get_current_datetime(_optional_timezone(payload))

    if name == "get_relative_datetime":
        _only(payload, {"days", "hours", "minutes", "timezone"})
        days, hours, minutes = _duration(payload)
        return get_relative_datetime(
            days=days,
            hours=hours,
            minutes=minutes,
            timezone=_optional_timezone(payload),
        )

    if name == "shift_datetime":
        _only(payload, {"datetime", "days", "hours", "minutes"})
        days, hours, minutes = _duration(payload)
        return shift_datetime(
            _required_string(payload, "datetime"),
            days=days,
            hours=hours,
            minutes=minutes,
        )

    if name == "get_weekday_for_explicit_date":
        _only(payload, {"date"})
        return get_weekday_for_explicit_date(_required_string(payload, "date"))

    if name == "set_reminder_mock":
        _only(payload, {"datetime", "message"})
        return set_reminder_mock(
            _required_string(payload, "datetime"),
            _required_string(payload, "message", max_length=500),
        )

    if name == "set_relative_reminder_mock":
        _only(payload, {"message", "days", "hours", "minutes", "timezone"})
        days, hours, minutes = _duration(payload)
        return set_relative_reminder_mock(
            _required_string(payload, "message", max_length=500),
            days=days,
            hours=hours,
            minutes=minutes,
            timezone=_optional_timezone(payload),
        )

    raise ValueError(f"unknown tool: {name}")


def _datetime_from_now(
    days: int,
    hours: int,
    minutes: int,
    timezone: str | None,
) -> tuple[dt.datetime, str]:
    zone = _zone(timezone or _default_timezone())
    value = dt.datetime.now(zone) + dt.timedelta(days=days, hours=hours, minutes=minutes)
    return value, zone.key


def _duration(payload: dict[str, Any]) -> tuple[int, int, int]:
    return (
        _integer(payload, "days", default=0, minimum=-36500, maximum=36500),
        _integer(payload, "hours", default=0, minimum=-876000, maximum=876000),
        _integer(payload, "minutes", default=0, minimum=-52560000, maximum=52560000),
    )


def _require_offset(days: int, hours: int, minutes: int) -> None:
    if days == 0 and hours == 0 and minutes == 0:
        raise ValueError("at least one non-zero time offset is required")


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


def _integer(
    payload: dict[str, Any],
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(name, default)
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
        "status": "mock_created",
        "persisted": False,
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
