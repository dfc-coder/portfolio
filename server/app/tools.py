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
            "Return the actual current date and time for a timezone. Use this function only when the "
            "requested answer depends on the present date or time, such as 'what date is it today?', "
            "'what time is it now?', 'tomorrow', 'yesterday', 'in 2 hours', or 'in 7 days'. This function "
            "does not perform relative date/time arithmetic. For a relative calculation, use the returned "
            "datetime as the base for add_duration_to_datetime before answering. Do not use this function "
            "for a fully specified calendar date, general knowledge, greetings, small talk, portfolio "
            "questions, or capability questions. The returned date, time, weekday, and timezone are "
            "authoritative."
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
            "Deterministically shift a supplied date or datetime by a signed duration and return the "
            "resulting datetime, calendar date, and weekday. Use positive values to move forward and "
            "negative values to move backward. Use this function for relative date/time arithmetic such "
            "as tomorrow, yesterday, 'in 15 days', '2 hours ago', or next week. Also use it to determine "
            "the weekday of a fully specified date; a zero duration is valid for that purpose. When the "
            "calculation is relative to the present, first obtain the actual current datetime with "
            "get_current_datetime and pass that exact datetime as the base. When the visitor already "
            "provides a fully specified date or datetime, use it directly and do not obtain the current "
            "datetime. Do not calculate dates or weekdays mentally. Reuse the returned values exactly."
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
                    "description": (
                        "Signed number of whole days to shift. Positive adds days; negative subtracts "
                        "days. Omit for zero."
                    ),
                },
                "hours": {
                    "type": "integer",
                    "minimum": -876000,
                    "maximum": 876000,
                    "description": (
                        "Signed number of whole hours to shift. Positive adds hours; negative subtracts "
                        "hours. Omit for zero."
                    ),
                },
                "minutes": {
                    "type": "integer",
                    "minimum": -52560000,
                    "maximum": 52560000,
                    "description": (
                        "Signed number of whole minutes to shift. Positive adds minutes; negative "
                        "subtracts minutes. Omit for zero."
                    ),
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
            "Create a simulated, non-persistent reminder for an already resolved absolute datetime. Use "
            "this function only when the visitor explicitly asks to create or set a reminder. A reminder "
            "request is not complete until this function has been called. The datetime argument must "
            "already be fully resolved. If the visitor specifies a relative time such as 'in 30 minutes', "
            "'in 2 hours', or 'in 7 days', first resolve the absolute datetime using the available "
            "date/time functions, then call this function. If the visitor already supplies a complete "
            "ISO-8601 datetime, call this function directly. Do not merely tell the visitor when the "
            "reminder would occur. This function does not persist data and does not schedule a real "
            "reminder."
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
