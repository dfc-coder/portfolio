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
            "Return the actual current date and time. This capability represents the current moment only "
            "and performs no date arithmetic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
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
            "Return the date, time, and weekday at a signed offset from the actual current moment. "
            "Use the same unit stated by the request instead of converting it. "
            "Tomorrow is offset 1 day; yesterday is offset -1 day."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "offset": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": (
                        "Signed quantity from now. Preserve the request magnitude: "
                        "in 2 hours uses 2, one week uses 1, 30 minutes ago uses -30."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": (
                        "Unit stated by the request. Choose exactly one of minutes, hours, days, or weeks."
                    ),
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
                },
            },
            "required": ["offset", "unit"],
            "additionalProperties": False,
        },
    },
}

SHIFT_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "shift_datetime",
        "description": (
            "Return details for a date or datetime supplied by the request after applying a signed offset. "
            "The base datetime must come from the request. Use offset 0 when only resolving the supplied "
            "date or weekday. Preserve the request unit instead of converting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": "ISO-8601 base date or datetime copied from the request.",
                },
                "offset": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Signed quantity applied to the supplied base datetime.",
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Unit for the offset: minutes, hours, days, or weeks.",
                },
            },
            "required": ["datetime", "offset", "unit"],
            "additionalProperties": False,
        },
    },
}

GET_WEEKDAY_FOR_EXPLICIT_DATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weekday_for_explicit_date",
        "description": (
            "Return the weekday for an exact calendar date that appears in the request. "
            "The date argument must be copied from the request, not inferred from relative language."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Exact ISO-8601 YYYY-MM-DD calendar date copied from the request.",
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
            "Simulate a non-persistent reminder at an absolute datetime supplied by the request. "
            "No real notification is scheduled or sent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": "Absolute ISO-8601 reminder datetime copied from the request.",
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

SET_RELATIVE_REMINDER_MOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_relative_reminder_mock",
        "description": (
            "Simulate a non-persistent reminder at a signed offset from the actual current moment. "
            "No real notification is scheduled or sent. Preserve the request magnitude and unit instead "
            "of converting between minutes, hours, days, and weeks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Reminder text without the relative scheduling phrase.",
                },
                "offset": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": (
                        "Signed quantity from now. In 30 minutes uses 30; in 2 hours uses 2; "
                        "in 7 days uses 7."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Unit stated by the request: minutes, hours, days, or weeks.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone. Omit to use the server timezone.",
                },
            },
            "required": ["message", "offset", "unit"],
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
    weeks: int = 0,
    timezone: str | None = None,
) -> dict[str, object]:
    _require_offset(days, hours, minutes, weeks)
    value, zone_name = _datetime_from_now(days, hours, minutes, weeks, timezone)
    return _datetime_result(value, zone_name)


def shift_datetime(
    datetime: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    weeks: int = 0,
    *,
    default_timezone: str | None = None,
) -> dict[str, object]:
    timezone = default_timezone or _default_timezone()
    value = _parse_datetime(datetime, timezone)
    shifted = value + dt.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)
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
    weeks: int = 0,
    timezone: str | None = None,
) -> dict[str, object]:
    _require_offset(days, hours, minutes, weeks)
    value, _ = _datetime_from_now(days, hours, minutes, weeks, timezone)
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
        duration = _model_duration(payload, allow_timezone=True)
        return get_relative_datetime(
            **duration,
            timezone=_optional_timezone(payload),
        )

    if name == "shift_datetime":
        datetime_value = _required_string(payload, "datetime")
        duration = _model_duration(payload, required={"datetime"})
        return shift_datetime(datetime_value, **duration)

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
        message = _required_string(payload, "message", max_length=500)
        duration = _model_duration(payload, required={"message"}, allow_timezone=True)
        return set_relative_reminder_mock(
            message,
            **duration,
            timezone=_optional_timezone(payload),
        )

    raise ValueError(f"unknown tool: {name}")


def _model_duration(
    payload: dict[str, Any],
    *,
    required: set[str] | None = None,
    allow_timezone: bool = False,
) -> dict[str, int]:
    required = required or set()
    allowed = required | {"offset", "unit"}
    if allow_timezone:
        allowed.add("timezone")

    legacy = {"days", "hours", "minutes"}
    if not ({"offset", "unit"} & set(payload)) and (legacy & set(payload)):
        legacy_allowed = required | legacy
        if allow_timezone:
            legacy_allowed.add("timezone")
        _only(payload, legacy_allowed)
        days, hours, minutes = _duration(payload)
        _require_offset(days, hours, minutes, 0)
        return {"days": days, "hours": hours, "minutes": minutes}

    _only(payload, allowed)
    offset = _required_integer(payload, "offset", minimum=-52560000, maximum=52560000)
    unit = _required_unit(payload)
    if offset == 0 and required != {"datetime"}:
        raise ValueError("offset must be non-zero")
    return {unit: offset}


def _datetime_from_now(
    days: int,
    hours: int,
    minutes: int,
    weeks: int,
    timezone: str | None,
) -> tuple[dt.datetime, str]:
    zone = _zone(timezone or _default_timezone())
    value = dt.datetime.now(zone) + dt.timedelta(
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
    )
    return value, zone.key


def _duration(payload: dict[str, Any]) -> tuple[int, int, int]:
    return (
        _integer(payload, "days", default=0, minimum=-36500, maximum=36500),
        _integer(payload, "hours", default=0, minimum=-876000, maximum=876000),
        _integer(payload, "minutes", default=0, minimum=-52560000, maximum=52560000),
    )


def _require_offset(days: int, hours: int, minutes: int, weeks: int) -> None:
    if days == 0 and hours == 0 and minutes == 0 and weeks == 0:
        raise ValueError("at least one non-zero time offset is required")


def _required_integer(
    payload: dict[str, Any],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if name not in payload:
        raise ValueError(f"{name} is required")
    return _integer(payload, name, default=0, minimum=minimum, maximum=maximum)


def _required_unit(payload: dict[str, Any]) -> str:
    value = payload.get("unit")
    if value not in _OFFSET_UNITS:
        raise ValueError(f"unit must be one of: {', '.join(_OFFSET_UNITS)}")
    return str(value)


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
