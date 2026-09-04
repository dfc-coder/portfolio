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
            "Return the actual current date and time for a timezone. Use it whenever the answer depends "
            "on what date or time it is now, including relative requests such as 'in two weeks'. It "
            "returns ISO datetime, date, weekday, Spanish weekday, and timezone fields. Treat those "
            "returned values as authoritative rather than estimating the current time yourself."
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

ADD_DURATION_TO_DATETIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_duration_to_datetime",
        "description": (
            "Add or subtract an exact duration from a supplied date or datetime. Use it for relative-date "
            "arithmetic and for weekday lookup instead of calculating dates mentally. A zero duration is "
            "valid when only the weekday of a known date is needed. It returns the exact resulting ISO "
            "datetime, calendar date, weekday, Spanish weekday, and timezone. Reuse these values exactly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "ISO-8601 date or datetime used as the calculation base, for example 2026-09-04 "
                        "or 2026-09-04T19:00:00-03:00. Date-only or timezone-less values use the server "
                        "default timezone."
                    ),
                },
                "days": {
                    "type": "integer",
                    "minimum": -36500,
                    "maximum": 36500,
                    "description": "Whole days to add or subtract. Omit for zero.",
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": "Whole hours to add or subtract. Omit for zero.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": "Whole minutes to add or subtract. Omit for zero.",
                },
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
            "Create a simulated reminder after its exact datetime has been resolved. Use it only when the "
            "visitor explicitly asks to set or create a reminder. It returns a mock reminder identifier "
            "and the supplied datetime/message, but it does not persist data or schedule a real reminder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": "Fully resolved ISO-8601 reminder datetime including a timezone offset.",
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

TOOLS = [
    SEARCH_PORTFOLIO_SCHEMA,
    GET_CURRENT_DATETIME_SCHEMA,
    ADD_DURATION_TO_DATETIME_SCHEMA,
    SET_REMINDER_MOCK_SCHEMA,
]


async def search_portfolio(portfolio: Portfolio, query: str) -> dict[str, object]:
    return {"facts": await portfolio.search(query)}


def get_current_datetime(timezone: str | None = None) -> dict[str, object]:
    zone = _zone(timezone or _default_timezone())
    return _datetime_result(dt.datetime.now(zone), zone.key)


def add_duration_to_datetime(
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


def set_reminder_mock(datetime: str, message: str) -> dict[str, object]:
    value = _aware_datetime(datetime)
    return {
        "reminder_id": f"mock-{uuid4()}",
        "datetime": value.isoformat(timespec="seconds"),
        "message": message,
        "status": "mock_created",
        "persisted": False,
    }


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
        timezone = payload.get("timezone")
        if timezone is not None and not isinstance(timezone, str):
            raise ValueError("timezone must be a string")
        if isinstance(timezone, str) and not timezone.strip():
            raise ValueError("timezone must not be empty")
        return get_current_datetime(timezone)

    if name == "add_duration_to_datetime":
        _only(payload, {"datetime", "days", "hours", "minutes"})
        datetime = _required_string(payload, "datetime")
        days = _integer(payload, "days", default=0, minimum=-36500, maximum=36500)
        hours = _integer(payload, "hours", default=0, minimum=-876000, maximum=876000)
        minutes = _integer(
            payload,
            "minutes",
            default=0,
            minimum=-52560000,
            maximum=52560000,
        )
        return add_duration_to_datetime(
            datetime,
            days=days,
            hours=hours,
            minutes=minutes,
        )

    if name == "set_reminder_mock":
        _only(payload, {"datetime", "message"})
        datetime = _required_string(payload, "datetime")
        message = _required_string(payload, "message", max_length=500)
        return set_reminder_mock(datetime, message)

    raise ValueError(f"unknown tool: {name}")


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
