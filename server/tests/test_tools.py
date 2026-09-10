import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from app.tools import TOOL_SCHEMAS, execute_tool, resolve_datetime, set_reminder_mock


class FakePortfolio:
    def __init__(self) -> None:
        self.queries = []

    async def search(self, query: str):
        self.queries.append(query)
        return [{"source": "profile", "text": query}]


def test_tool_schemas_have_expected_names() -> None:
    assert [item["function"]["name"] for item in TOOL_SCHEMAS] == [
        "search_portfolio",
        "resolve_datetime",
        "set_reminder_mock",
    ]


def test_resolve_datetime_explicit_date() -> None:
    result = resolve_datetime(
        "2026-12-25",
        0,
        "days",
        "America/Argentina/Buenos_Aires",
    )

    assert result["date"] == "2026-12-25"
    assert result["weekday_es"] == "viernes"


def test_resolve_datetime_relative_offset() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(hours=3)

    result = resolve_datetime("now", 3, "hours", zone.key)

    after = dt.datetime.now(zone) + dt.timedelta(hours=3)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)


def test_reminder_is_simulated_only() -> None:
    result = set_reminder_mock(
        "2026-09-10T15:00:00-03:00",
        0,
        "minutes",
        "Revisar demo",
    )

    assert result["status"] == "simulated_only"
    assert result["persisted"] is False
    assert result["will_notify"] is False


@pytest.mark.asyncio
async def test_execute_search_portfolio() -> None:
    portfolio = FakePortfolio()

    body = await execute_tool(
        "search_portfolio",
        '{"query":"Rust"}',
        portfolio,
    )

    assert body["ok"] is True
    assert portfolio.queries == ["Rust"]


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected() -> None:
    body = await execute_tool("unknown", "{}", FakePortfolio())

    assert body == {
        "ok": False,
        "error": {
            "type": "validation_error",
            "message": "unknown tool: unknown",
        },
    }


@pytest.mark.asyncio
async def test_invalid_json_is_rejected() -> None:
    body = await execute_tool("search_portfolio", "{", FakePortfolio())

    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"


@pytest.mark.asyncio
async def test_missing_required_argument_is_rejected() -> None:
    body = await execute_tool(
        "resolve_datetime",
        '{"reference":"now","unit":"days"}',
        FakePortfolio(),
    )

    assert body["ok"] is False
    assert body["error"]["message"] == "offset is required"


@pytest.mark.asyncio
async def test_extra_argument_is_rejected() -> None:
    portfolio = FakePortfolio()

    body = await execute_tool(
        "search_portfolio",
        '{"query":"Rust","extra":1}',
        portfolio,
    )

    assert body["ok"] is False
    assert "unexpected tool argument" in body["error"]["message"]
    assert portfolio.queries == []


@pytest.mark.asyncio
async def test_invalid_timezone_is_rejected_before_execution() -> None:
    body = await execute_tool(
        "resolve_datetime",
        json.dumps(
            {
                "reference": "now",
                "offset": 0,
                "unit": "days",
                "timezone": "No/Such_Zone",
            }
        ),
        FakePortfolio(),
    )

    assert body["ok"] is False
    assert "unknown timezone" in body["error"]["message"]
