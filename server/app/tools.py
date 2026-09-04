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
        description=(
            "Semantic search query describing the portfolio or CV facts needed to answer "
            "the visitor."
        ),
    )


class CurrentDatetimeArgs(ToolArgs):
    timezone: str | None = Field(
        default=None,
        description=(
            "Optional IANA timezone such as America/Argentina/Buenos_Aires. "
            "Omit it to use the application's default timezone."
        ),
    )


class AddDurationArgs(ToolArgs):
    datetime: str = Field(description="ISO-8601 datetime including a timezone offset.")
    days: int = Field(
        default=0,
        ge=-36500,
        le=36500,
        description="Whole days to add. Use a negative value to subtract days.",
    )
    hours: int = Field(
        default=0,
        ge=-876000,
        le=876000,
        description="Whole hours to add. Use a negative value to subtract hours.",
    )
    minutes: int = Field(
        default=0,
        ge=-52560000,
        le=52560000,
        description="Whole minutes to add. Use a negative value to subtract minutes.",
    )


class SetReminderArgs(ToolArgs):
    datetime: str = Field(description="ISO-8601 datetime including a timezone offset.")
    message: str = Field(
        min_length=1,
        max_length=500,
        description="Text of the simulated reminder.",
    )


def _schema(name: str, description: str, args: type[ToolArgs]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": args.model_json_schema(),
        },
    }


search_portfolio_schema = _schema(
    "search_portfolio",
    (
        "Searches the professional portfolio and CV for factual evidence. "
        "Use it before making factual claims about the professional's experience, skills, "
        "projects, education, certifications, services or background. "
        "It returns relevant profile passages together with source identifiers."
    ),
    SearchPortfolioArgs,
)

get_current_datetime_schema = _schema(
    "get_current_datetime",
    (
        "Returns the actual current date and time in an IANA timezone. "
        "Use it whenever the answer depends on what date or time it is now, especially for "
        "relative requests such as 'in two weeks'. "
        "It returns an ISO-8601 datetime and the timezone used."
    ),
    CurrentDatetimeArgs,
)

add_duration_to_datetime_schema = _schema(
    "add_duration_to_datetime",
    (
        "Adds or subtracts an exact duration from an ISO-8601 datetime. "
        "Use it for date arithmetic instead of calculating relative dates mentally. "
        "It accepts days, hours and minutes and returns the resulting ISO-8601 datetime."
    ),
    AddDurationArgs,
)

set_reminder_mock_schema = _schema(
    "set_reminder_mock",
    (
        "Creates a simulated reminder for exercising the agent tool workflow. "
        "Use it only after the requested reminder datetime is fully resolved. "
        "It does not persist data or create a real reminder, and returns a mock identifier "
        "plus the simulated reminder details."
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


def get_current_datetime(timezone: str | None, default_timezone: str) -> dict[str, str]:
    zone_name = timezone or default_timezone
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {zone_name}") from exc

    return {
        "datetime": dt.datetime.now(zone).isoformat(timespec="seconds"),
        "timezone": zone.key,
    }


def add_duration_to_datetime(
    datetime: str,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
) -> dict[str, str]:
    value = _aware_datetime(datetime)
    result = value + dt.timedelta(days=days, hours=hours, minutes=minutes)
    return {"datetime": result.isoformat(timespec="seconds")}


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
            "error": {
                "type": "validation_error",
                "message": str(exc),
            },
        }
    except Exception as exc:
        body = {
            "ok": False,
            "error": {
                "type": "tool_error",
                "message": str(exc),
            },
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
        return add_duration_to_datetime(**args.model_dump())

    if name == "set_reminder_mock":
        args = SetReminderArgs.model_validate(payload)
        return set_reminder_mock(**args.model_dump())

    raise ValueError(f"unknown tool: {name}")


def _aware_datetime(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("datetime must be valid ISO-8601") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return parsed
