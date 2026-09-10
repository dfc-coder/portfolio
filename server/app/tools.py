from __future__ import annotations

import datetime as dt
import json
import logging
import os
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .portfolio import Portfolio

SEARCH_PORTFOLIO = "search_portfolio"
RESOLVE_DATETIME = "resolve_datetime"
SET_REMINDER_MOCK = "set_reminder_mock"

_WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
_OFFSET_UNITS = ("minutes", "hours", "days", "weeks")

logger = logging.getLogger(__name__)

SEARCH_PORTFOLIO_SCHEMA = {
    "type": "function",
    "function": {
        "name": SEARCH_PORTFOLIO,
        "description": (
            "Search factual professional information about the portfolio subject. Use it before stating claims "
            "about experience, skills, projects, education, certifications, services, or professional background. "
            "Do not use it for general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": (
                        "Short query containing only the specific professional fact or topic to retrieve. "
                        "Omit the portfolio subject's name unless identity itself is the requested fact."
                    ),
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
        "name": RESOLVE_DATETIME,
        "description": (
            "Resolve current, relative, or explicit date and time calculations, including weekday and timezone "
            "questions. This tool is read-only and never creates reminders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Use 'now' when there is no explicit date or time. Otherwise use an ISO-8601 value. "
                        "Use YYYY-MM-DD for a date without a time."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Relative amount applied to reference. Examples: tomorrow=1 day, yesterday=-1 day, "
                        "in one week=1 week, in two hours=2 hours. Use 0 for the reference itself."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Unit for offset: minutes, hours, days, or weeks.",
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
        "name": SET_REMINDER_MOCK,
        "description": (
            "Create a simulated, non-persistent reminder when the visitor asks to be reminded. It never schedules "
            "or sends a real notification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": (
                        "Use 'now' for a relative reminder. Otherwise use the explicit date or time as ISO-8601."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Relative amount applied to reference. Examples: in 30 minutes=30 minutes, "
                        "in two hours=2 hours, in seven days=7 days. Use 0 for an explicit absolute schedule."
                    ),
                },
                "unit": {
                    "type": "string",
                    "enum": list(_OFFSET_UNITS),
                    "description": "Unit for offset: minutes, hours, days, or weeks.",
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

TOOL_SCHEMAS = (
    SEARCH_PORTFOLIO_SCHEMA,
    RESOLVE_DATETIME_SCHEMA,
    SET_REMINDER_MOCK_SCHEMA,
)


async def execute_tool(
    name: str,
    raw_arguments: str,
    portfolio: Portfolio,
) -> dict[str, object]:
    try:
        arguments = json.loads(raw_arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be a JSON object")

        if name == SEARCH_PORTFOLIO:
            _only(arguments, {"query"})
            result = {
                "facts": await portfolio.search(
                    _required_string(arguments, "query", max_length=500)
                )
            }
        elif name == RESOLVE_DATETIME:
            _only(arguments, {"reference", "offset", "unit", "timezone"})
            result = resolve_datetime(
                reference=_required_string(arguments, "reference", max_length=100),
                offset=_required_integer(
                    arguments,
                    "offset",
                    minimum=-52560000,
                    maximum=52560000,
                ),
                unit=_required_choice(arguments, "unit", _OFFSET_UNITS),
                timezone=_optional_timezone(arguments),
            )
        elif name == SET_REMINDER_MOCK:
            _only(arguments, {"reference", "offset", "unit", "message", "timezone"})
            result = set_reminder_mock(
                reference=_required_string(arguments, "reference", max_length=100),
                offset=_required_integer(
                    arguments,
                    "offset",
                    minimum=-52560000,
                    maximum=52560000,
                ),
                unit=_required_choice(arguments, "unit", _OFFSET_UNITS),
                message=_required_string(arguments, "message", max_length=500),
                timezone=_optional_timezone(arguments),
            )
        else:
            raise ValueError(f"unknown tool: {name}")

        return {"ok": True, "result": result}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {
            "ok": False,
            "error": {"type": "validation_error", "message": str(exc)},
        }
    except Exception:
        logger.exception("tool execution failed: %s", name)
        return {
            "ok": False,
            "error": {"type": "tool_error", "message": "tool execution failed"},
        }


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
    return {
        "reminder_id": f"mock-{uuid4()}",
        "datetime": (value + _offset_delta(offset, unit)).isoformat(timespec="seconds"),
        "message": message,
        "status": "simulated_only",
        "persisted": False,
        "will_notify": False,
    }


def _resolve_reference(reference: str, timezone: str | None) -> tuple[dt.datetime, str]:
    zone_name = timezone or os.getenv("TZ", _DEFAULT_TIMEZONE)
    if reference == "now":
        zone = _zone(zone_name)
        return dt.datetime.now(zone), zone.key

    value = _parse_datetime(reference, zone_name)
    return value, getattr(value.tzinfo, "key", None) or value.tzname() or zone_name


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
        raise ValueError("reference must be 'now' or valid ISO-8601") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=zone)
    return parsed


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc


def _optional_timezone(arguments: dict[str, Any]) -> str | None:
    value = arguments.get("timezone")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timezone must be a non-empty string")
    _zone(value)
    return value


def _only(arguments: dict[str, Any], allowed: set[str]) -> None:
    extra = set(arguments) - allowed
    if extra:
        raise ValueError(f"unexpected tool argument: {sorted(extra)[0]}")


def _required_string(
    arguments: dict[str, Any],
    name: str,
    *,
    max_length: int | None = None,
) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{name} must be at most {max_length} characters")
    return value


def _required_integer(
    arguments: dict[str, Any],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if name not in arguments:
        raise ValueError(f"{name} is required")
    value = arguments[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _required_choice(
    arguments: dict[str, Any],
    name: str,
    allowed: tuple[str, ...],
) -> str:
    value = arguments.get(name)
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return str(value)
