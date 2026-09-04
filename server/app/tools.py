from __future__ import annotations

import datetime as dt
import json
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .portfolio import Portfolio


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchPortfolioArgs(ToolArgs):
    query: str = Field(
        min_length=1,
        max_length=500,
        description="Portfolio/CV facts or topic to search for.",
    )


class CurrentDatetimeArgs(ToolArgs):
    timezone: str | None = Field(
        default=None,
        description="Optional IANA timezone. Omit it to use the application timezone.",
    )


class AddDurationArgs(ToolArgs):
    datetime: str = Field(
        description=(
            "ISO-8601 date or datetime. Date-only or timezone-less values use the "
            "application timezone."
        )
    )
    days: int = Field(default=0, ge=-36500, le=36500, description="Whole days to add.")
    hours: int = Field(default=0, ge=-876000, le=876000, description="Whole hours to add.")
    minutes: int = Field(
        default=0,
        ge=-52560000,
        le=52560000,
        description="Whole minutes to add.",
    )


class SetReminderArgs(ToolArgs):
    datetime: str = Field(description="ISO-8601 datetime including a timezone offset.")
    message: str = Field(min_length=1, max_length=500, description="Reminder text.")


def _schema(name: str, description: str, args: type[ToolArgs]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": _strip_titles(args.model_json_schema()),
        },
    }


def _strip_titles(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_titles(item) for key, item in value.items() if key != "title"}
    if isinstance(value, list):
        return [_strip_titles(item) for item in value]
    return value


search_portfolio_schema = _schema(
    "search_portfolio",
    (
        "Search the professional portfolio/CV for factual evidence. Use only when the visitor "
        "explicitly asks about the professional's experience, skills, projects, education, "
        "certifications, services or background. Do not use for greetings, thanks or small talk."
    ),
    SearchPortfolioArgs,
)

get_current_datetime_schema = _schema(
    "get_current_datetime",
    (
        "Return the actual current date and time. Use whenever the answer depends on what date "
        "or time it is now, including relative requests such as 'in two weeks'."
    ),
    CurrentDatetimeArgs,
)

add_duration_to_datetime_schema = _schema(
    "add_duration_to_datetime",
    (
        "Add or subtract a duration from a date/datetime and return the exact resulting date and "
        "weekday. Use for date arithmetic and also to determine the weekday of a known date by "
        "passing zero duration. Do not calculate calendar dates or weekdays mentally."
    ),
    AddDurationArgs,
)

set_reminder_mock_schema = _schema(
    "set_reminder_mock",
    (
        "Create a simulated reminder after its datetime is fully resolved. It does not persist "
        "anything or create a real reminder."
    ),
    SetReminderArgs,
)

TOOLS = [
    search_portfolio_schema,
    get_current_datetime_schema,
    add_duration_to_datetime_schema,
    set_reminder_mock_schema,
]


async def search_portfolio(portfolio: Portfolio, query: str) -> dict[str, object]:
    return {"facts": await portfolio.search(query)}


def get_current_datetime(timezone: str | None, default_timezone: str) -> dict[str, object]:
    zone = _zone(timezone or default_timezone)
    return _datetime_result(dt.datetime.now(zone), zone.key)


def add_duration_to_datetime(
    datetime: str,
    default_timezone: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
) -> dict[str, object]:
    value = _parse_datetime(datetime, default_timezone)
    result = value + dt.timedelta(days=days, hours=hours, minutes=minutes)
    zone_name = getattr(result.tzinfo, "key", None) or result.tzname() or default_timezone
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
    default_timezone: str,
) -> dict[str, str]:
    try:
        payload = json.loads(raw_arguments or "{}")
        if not isinstance(payload, dict):
            raise ValueError("tool arguments must be a JSON object")
        result = await _run_tool(name, payload, portfolio, default_timezone)
        body: dict[str, object] = {"ok": True, "result": result}
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
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
    default_timezone: str,
) -> object:
    if name == "search_portfolio":
        args = SearchPortfolioArgs.model_validate(payload)
        return await search_portfolio(portfolio, args.query)

    if name == "get_current_datetime":
        args = CurrentDatetimeArgs.model_validate(payload)
        return get_current_datetime(args.timezone, default_timezone)

    if name == "add_duration_to_datetime":
        args = AddDurationArgs.model_validate(payload)
        return add_duration_to_datetime(
            default_timezone=default_timezone,
            **args.model_dump(),
        )

    if name == "set_reminder_mock":
        args = SetReminderArgs.model_validate(payload)
        return set_reminder_mock(**args.model_dump())

    raise ValueError(f"unknown tool: {name}")


def _datetime_result(value: dt.datetime, timezone: str) -> dict[str, object]:
    return {
        "datetime": value.isoformat(timespec="seconds"),
        "date": value.date().isoformat(),
        "weekday": value.strftime("%A"),
        "iso_weekday": value.isoweekday(),
        "timezone": timezone,
    }


def _parse_datetime(value: str, default_timezone: str) -> dt.datetime:
    zone = _zone(default_timezone)
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


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc
