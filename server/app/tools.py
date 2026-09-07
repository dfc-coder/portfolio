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
            "Search the professional portfolio and CV for factual evidence. Use it when the visitor "
            "asks about the professional's experience, skills, projects, education, certifications, "
            "services, or background. Do not use it for greetings, thanks, or unrelated small talk. "
            "It returns relevant profile passages with source identifiers. An empty result means the "
            "available profile does not confirm the fact; it is not proof that the professional lacks it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": (
                        "A concise search query for the exact professional fact needed, for example "
                        "'Rust projects', 'AWS experience', or 'education'."
                    ),
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
            "Return the actual current date and time for a timezone. Use when the visitor explicitly "
            "asks for today's date or the current time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone such as America/Argentina/Buenos_Aires. Omit it when the "
                        "visitor did not request another timezone; the server default timezone is used."
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
            "Resolve a date or time relative to the actual present moment. Use for tomorrow, yesterday, "
            "in N days or hours, N days or hours ago, next week, and for the weekday of a relative date. "
            "Returns the exact resulting datetime, date, and weekday."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole days relative to now. Positive is future; negative is past.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole hours relative to now. Positive is future; negative is past.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole minutes relative to now. Positive is future; negative is past.",
                },
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone. Omit when the visitor did not request another timezone; "
                        "the server default timezone is used."
                    ),
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
            "Move a supplied explicit date or datetime forward or backward by a signed duration. Use when "
            "the visitor provides the base date or datetime and asks to add or subtract days, hours, or "
            "minutes. Positive values move forward and negative values move backward."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "ISO-8601 base date or datetime, for example 2026-12-25 or "
                        "2026-09-07T12:30:00-03:00. Date-only or timezone-less values use the server "
                        "default timezone."
                    ),
                },
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole days to shift. Positive adds; negative subtracts.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole hours to shift. Positive adds; negative subtracts.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole minutes to shift. Positive adds; negative subtracts.",
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
            "Return the weekday for an explicit calendar date supplied by the visitor. The input must be "
            "a concrete ISO-8601 date or datetime such as 2026-12-25."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "Explicit ISO-8601 date or datetime whose weekday is required, for example "
                        "2026-12-25 or 2026-12-25T15:00:00-03:00. Date-only or timezone-less values use "
                        "the server default timezone."
                    ),
                }
            },
            "required": ["datetime"],
            "additionalProperties": False,
        },
    },
}

SET_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_reminder_mock",
        "description": (
            "Create a simulated, non-persistent reminder for an explicit absolute datetime supplied by "
            "the visitor. Use only when the reminder time is already an absolute ISO-8601 datetime. Do not "
            "use for relative reminder requests such as 'in 30 minutes' or 'in 7 days'; use "
            "set_relative_reminder_mock for those."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "Fully resolved ISO-8601 reminder datetime including a timezone offset, for "
                        "example 2026-09-10T15:00:00-03:00."
                    ),
                },
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Short text describing what the simulated reminder should say.",
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
            "Create a simulated, non-persistent reminder at a time relative to the actual present moment "
            "in one operation. Use for explicit reminder requests such as 'remind me in 30 minutes', "
            "'remind me in 2 hours', or 'remind me in 7 days'. This function already resolves the current "
            "datetime and applies the relative offset, so do not call get_current_datetime, "
            "get_relative_datetime, or shift_datetime first. Use set_reminder_mock instead when the visitor "
            "supplies an absolute ISO-8601 reminder datetime."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Short text describing what the simulated reminder should say.",
                },
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Signed whole days relative to now.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Signed whole hours relative to now.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed whole minutes relative to now.",
                },
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone. Omit when the visitor did not request another timezone; "
                        "the server default timezone is used."
                    ),
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
    zone_name = timezone or _default_timezone()
    base = get_current_datetime(zone_name)
    return shift_datetime(
        str(base["datetime"]),
        days=days,
        hours=hours,
        minutes=minutes,
        default_timezone=zone_name,
    )


def shift_datetime(
    datetime: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    *,
    default_timezone: str | None = None,
) -> dict[str, object]:
    timezone = default_timezone or _default_timezone()
    value = _parse_datetime(datetime, timezone)
    result = value + dt.timedelta(days=days, hours=hours, minutes=minutes)
    zone_name = getattr(result.tzinfo, "key", None) or result.tzname() or timezone
    return _datetime_result(result, zone_name)


def get_datetime_weekday(
    datetime: str,
    *,
    default_timezone: str | None = None,
) -> dict[str, object]:
    timezone = default_timezone or _default_timezone()
    value = _parse_datetime(datetime, timezone)
    zone_name = getattr(value.tzinfo, "key", None) or value.tzname() or timezone
    return _datetime_result(value, zone_name)


def set_reminder_mock(datetime: str, message: str) -> dict[str, object]:
    value = _aware_datetime(datetime)
    return {
        "reminder_id": f"mock-{uuid4()}",
        "datetime": value.isoformat(timespec="seconds"),
        "message": message,
        "status": "mock_created",
        "persisted": False,
    }


def set_relative_reminder_mock(
    message: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    timezone: str | None = None,
) -> dict[str, object]:
    target = get_relative_datetime(
        days=days,
        hours=hours,
        minutes=minutes,
        timezone=timezone,
    )
    return set_reminder_mock(str(target["datetime"]), message)


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
        datetime = _required_string(payload, "datetime")
        days, hours, minutes = _duration(payload)
        return shift_datetime(
            datetime,
            days=days,
            hours=hours,
            minutes=minutes,
        )

    if name == "get_weekday_for_explicit_date":
        _only(payload, {"datetime"})
        datetime = _required_string(payload, "datetime")
        return get_datetime_weekday(datetime)

    if name == "set_reminder_mock":
        _only(payload, {"datetime", "message"})
        datetime = _required_string(payload, "datetime")
        message = _required_string(payload, "message", max_length=500)
        return set_reminder_mock(datetime, message)

    if name == "set_relative_reminder_mock":
        _only(payload, {"message", "days", "hours", "minutes", "timezone"})
        message = _required_string(payload, "message", max_length=500)
        days, hours, minutes = _duration(payload)
        return set_relative_reminder_mock(
            message,
            days=days,
            hours=hours,
            minutes=minutes,
            timezone=_optional_timezone(payload),
        )

    raise ValueError(f"unknown tool: {name}")


def _duration(payload: dict[str, Any]) -> tuple[int, int, int]:
    return (
        _integer(payload, "days", default=0, minimum=-36500, maximum=36500),
        _integer(payload, "hours", default=0, minimum=-876000, maximum=876000),
        _integer(payload, "minutes", default=0, minimum=-52560000, maximum=52560000),
    )


def _optional_timezone(payload: dict[str, Any]) -> str | None:
    timezone = payload.get("timezone")
    if timezone is None:
        return None
    if not isinstance(timezone, str):
        raise ValueError("timezone must be a string")
    if not timezone.strip():
        raise ValueError("timezone must not be empty")
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


def _datetime_result(value: dt.datetime, timezone: str) -> dict[str, object]:
    return {
        "datetime": value.isoformat(timespec="seconds"),
        "date": value.date().isoformat(),
        "weekday": value.strftime("%A"),
        "weekday_es": _WEEKDAYS_ES[value.weekday()],
        "iso_weekday": value.isoweekday(),
        "timezone": timezone,
    }


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
