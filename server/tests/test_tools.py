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


def test_tool_schemas_are_small_and_explicit() -> None:
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
    assert resolve_parameters["required"] == ["base", "offset", "unit"]
    assert resolve_parameters["properties"]["base"]["enum"] == ["now", "provided"]
    assert resolve_parameters["properties"]["unit"]["enum"] == [
        "minutes",
        "hours",
        "days",
        "weeks",
    ]
    assert TOOLS[2]["function"]["parameters"]["required"] == ["datetime", "message"]


def test_resolve_datetime_uses_current_time_as_base() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(days=1)

    result = resolve_datetime(
        base="now",
        offset=1,
        unit="days",
        timezone="America/Argentina/Buenos_Aires",
    )

    after = dt.datetime.now(zone) + dt.timedelta(days=1)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)
    assert result["timezone"] == "America/Argentina/Buenos_Aires"


def test_resolve_datetime_supports_equivalent_duration_units() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    one = resolve_datetime(
        base="now",
        offset=2,
        unit="hours",
        timezone=zone.key,
    )
    two = resolve_datetime(
        base="now",
        offset=120,
        unit="minutes",
        timezone=zone.key,
    )

    first = dt.datetime.fromisoformat(str(one["datetime"]))
    second = dt.datetime.fromisoformat(str(two["datetime"]))
    assert abs((first - second).total_seconds()) <= 1


def test_resolve_datetime_handles_supplied_date_without_arithmetic() -> None:
    result = resolve_datetime(
        base="provided",
        datetime="2026-12-25",
        offset=0,
        unit="days",
        timezone="America/Argentina/Buenos_Aires",
    )

    assert result["date"] == "2026-12-25"
    assert result["weekday"] == "Friday"
    assert result["weekday_es"] == "viernes"
    assert result["iso_weekday"] == 5


def test_resolve_datetime_requires_base_consistency() -> None:
    with pytest.raises(ValueError, match="omitted"):
        resolve_datetime(
            base="now",
            datetime="2026-12-25",
            offset=0,
            unit="days",
        )

    with pytest.raises(ValueError, match="required"):
        resolve_datetime(
            base="provided",
            offset=0,
            unit="days",
        )


def test_reminder_result_is_explicitly_simulated() -> None:
    result = set_reminder_mock(
        "2026-09-10T15:00:00-03:00",
        "Revisar demo",
    )

    assert result["datetime"] == "2026-09-10T15:00:00-03:00"
    assert result["message"] == "Revisar demo"
    assert result["status"] == "simulated_only"
    assert result["persisted"] is False
    assert result["will_notify"] is False


@pytest.mark.asyncio
async def test_model_resolve_contract_accepts_relative_time() -> None:
    message = await run_tool_call(
        "call-resolve",
        "resolve_datetime",
        json.dumps({"base": "now", "offset": 1, "unit": "weeks"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is True
    target = dt.datetime.fromisoformat(body["result"]["datetime"])
    now = dt.datetime.now(target.tzinfo)
    assert dt.timedelta(days=6, hours=23) < target - now < dt.timedelta(days=7, minutes=1)


@pytest.mark.asyncio
async def test_model_resolve_contract_accepts_supplied_date() -> None:
    message = await run_tool_call(
        "call-date",
        "resolve_datetime",
        json.dumps(
            {
                "base": "provided",
                "datetime": "2026-01-01",
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
async def test_tool_validation_rejects_invented_datetime_for_now_base() -> None:
    message = await run_tool_call(
        "call-bad-base",
        "resolve_datetime",
        json.dumps(
            {
                "base": "now",
                "datetime": "2024-12-17",
                "offset": -1,
                "unit": "days",
            }
        ),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "omitted" in body["error"]["message"]


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
async def test_tool_validation_rejects_wrong_offset_type() -> None:
    message = await run_tool_call(
        "call-offset",
        "resolve_datetime",
        json.dumps({"base": "now", "offset": "15", "unit": "days"}),
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
        json.dumps({"base": "now", "offset": 2, "unit": "fortnights"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unit must be one of" in body["error"]["message"]
