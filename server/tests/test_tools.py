import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from app.tools import (
    TOOLS,
    resolve_datetime,
    run_tool_call,
    set_reminder_mock,
)


class FakePortfolio:
    async def search(self, query: str):
        return [{"source": "projects.0", "text": f"fact for {query}"}]


def test_tool_schemas_are_small_explicit_and_registry_ordered() -> None:
    names = [tool["function"]["name"] for tool in TOOLS]

    assert names == [
        "search_portfolio",
        "resolve_datetime",
        "set_reminder_mock",
    ]

    for tool in TOOLS:
        function = tool["function"]
        parameters = function["parameters"]
        assert tool["type"] == "function"
        assert function["description"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert "title" not in parameters
        assert "$defs" not in parameters

    resolve_parameters = TOOLS[1]["function"]["parameters"]
    assert resolve_parameters["required"] == ["reference", "offset", "unit"]
    assert resolve_parameters["properties"]["unit"]["enum"] == [
        "minutes",
        "hours",
        "days",
        "weeks",
    ]

    reminder_parameters = TOOLS[2]["function"]["parameters"]
    assert reminder_parameters["required"] == [
        "reference",
        "offset",
        "unit",
        "message",
    ]


def test_resolve_datetime_uses_now_reference() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(days=1)

    result = resolve_datetime(
        reference="now",
        offset=1,
        unit="days",
        timezone=zone.key,
    )

    after = dt.datetime.now(zone) + dt.timedelta(days=1)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)
    assert result["timezone"] == zone.key


def test_resolve_datetime_supports_equivalent_duration_units() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    one = resolve_datetime(
        reference="now",
        offset=2,
        unit="hours",
        timezone=zone.key,
    )
    two = resolve_datetime(
        reference="now",
        offset=120,
        unit="minutes",
        timezone=zone.key,
    )

    first = dt.datetime.fromisoformat(str(one["datetime"]))
    second = dt.datetime.fromisoformat(str(two["datetime"]))
    assert abs((first - second).total_seconds()) <= 1


def test_resolve_datetime_uses_explicit_reference_without_arithmetic() -> None:
    result = resolve_datetime(
        reference="2026-12-25",
        offset=0,
        unit="days",
        timezone="America/Argentina/Buenos_Aires",
    )

    assert result["date"] == "2026-12-25"
    assert result["weekday"] == "Friday"
    assert result["weekday_es"] == "viernes"
    assert result["iso_weekday"] == 5


def test_relative_reminder_resolves_schedule_in_one_call() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(minutes=30)

    result = set_reminder_mock(
        reference="now",
        offset=30,
        unit="minutes",
        message="Revisar portfolio",
        timezone=zone.key,
    )

    after = dt.datetime.now(zone) + dt.timedelta(minutes=30)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)
    assert result["message"] == "Revisar portfolio"
    assert result["status"] == "simulated_only"
    assert result["persisted"] is False
    assert result["will_notify"] is False


def test_explicit_reminder_uses_explicit_reference() -> None:
    result = set_reminder_mock(
        reference="2026-09-10T15:00:00-03:00",
        offset=0,
        unit="minutes",
        message="Revisar demo",
    )

    assert result["datetime"] == "2026-09-10T15:00:00-03:00"
    assert result["message"] == "Revisar demo"
    assert result["persisted"] is False
    assert result["will_notify"] is False


@pytest.mark.asyncio
async def test_model_resolve_contract_accepts_relative_time() -> None:
    message = await run_tool_call(
        "call-resolve",
        "resolve_datetime",
        json.dumps({"reference": "now", "offset": 1, "unit": "weeks"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is True
    target = dt.datetime.fromisoformat(body["result"]["datetime"])
    now = dt.datetime.now(target.tzinfo)
    assert dt.timedelta(days=6, hours=23) < target - now < dt.timedelta(days=7, minutes=1)


@pytest.mark.asyncio
async def test_model_resolve_contract_accepts_explicit_date() -> None:
    message = await run_tool_call(
        "call-date",
        "resolve_datetime",
        json.dumps(
            {
                "reference": "2026-01-01",
                "offset": 0,
                "unit": "days",
            }
        ),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is True
    assert body["result"]["weekday_es"] == "jueves"


@pytest.mark.asyncio
async def test_model_reminder_contract_accepts_relative_schedule() -> None:
    message = await run_tool_call(
        "call-reminder",
        "set_reminder_mock",
        json.dumps(
            {
                "reference": "now",
                "offset": 2,
                "unit": "hours",
                "message": "Enviar CV",
            }
        ),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is True
    assert body["result"]["message"] == "Enviar CV"
    assert body["result"]["will_notify"] is False


@pytest.mark.asyncio
async def test_tool_validation_rejects_invalid_reference() -> None:
    message = await run_tool_call(
        "call-reference",
        "resolve_datetime",
        json.dumps({"reference": "not-a-date", "offset": 0, "unit": "days"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "reference" in body["error"]["message"]


@pytest.mark.asyncio
async def test_tool_validation_rejects_unknown_arguments() -> None:
    message = await run_tool_call(
        "call-extra",
        "search_portfolio",
        json.dumps({"query": "Rust", "unexpected": True}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unexpected tool argument" in body["error"]["message"]


@pytest.mark.asyncio
async def test_tool_validation_rejects_unknown_tool() -> None:
    message = await run_tool_call(
        "call-unknown",
        "unknown_tool",
        "{}",
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"] == {
        "type": "validation_error",
        "message": "unknown tool: unknown_tool",
    }


@pytest.mark.asyncio
async def test_tool_validation_rejects_wrong_offset_type() -> None:
    message = await run_tool_call(
        "call-offset",
        "resolve_datetime",
        json.dumps({"reference": "now", "offset": "15", "unit": "days"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["message"] == "offset must be an integer"


@pytest.mark.asyncio
async def test_tool_validation_rejects_unknown_unit() -> None:
    message = await run_tool_call(
        "call-unit",
        "resolve_datetime",
        json.dumps({"reference": "now", "offset": 2, "unit": "fortnights"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unit must be one of" in body["error"]["message"]
