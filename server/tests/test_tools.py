import json

import pytest

from app.tools import TOOLS, add_duration_to_datetime, run_tool_call


class FakePortfolio:
    async def search(self, query: str):
        return [{"source": "projects.0", "text": f"fact for {query}"}]


def test_tool_schemas_are_explicit_json_schema() -> None:
    names = [tool["function"]["name"] for tool in TOOLS]

    assert names == [
        "search_portfolio",
        "get_current_datetime",
        "add_duration_to_datetime",
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

    assert TOOLS[0]["function"]["parameters"]["required"] == ["query"]
    assert TOOLS[2]["function"]["parameters"]["required"] == ["datetime"]
    assert TOOLS[3]["function"]["parameters"]["required"] == ["datetime", "message"]


def test_add_duration_calculates_date_and_weekday_exactly() -> None:
    result = add_duration_to_datetime(
        "2026-09-04",
        default_timezone="America/Argentina/Buenos_Aires",
        days=15,
    )

    assert result["date"] == "2026-09-19"
    assert result["weekday"] == "Saturday"
    assert result["weekday_es"] == "sábado"
    assert result["iso_weekday"] == 6
    assert result["timezone"] == "America/Argentina/Buenos_Aires"


def test_add_duration_accepts_naive_datetime_in_default_timezone() -> None:
    result = add_duration_to_datetime(
        "2030-01-02T10:30:00",
        default_timezone="America/Argentina/Buenos_Aires",
        days=57,
        hours=2,
        minutes=15,
    )

    assert result["datetime"] == "2030-02-28T12:45:00-03:00"


@pytest.mark.asyncio
async def test_tool_validation_error_is_returned_to_model() -> None:
    message = await run_tool_call(
        "call-1",
        "add_duration_to_datetime",
        json.dumps({"datetime": "not-a-date", "days": 2}),
        FakePortfolio(),
        "America/Argentina/Buenos_Aires",
    )

    body = json.loads(message["content"])
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call-1"
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"


@pytest.mark.asyncio
async def test_tool_validation_rejects_unknown_arguments() -> None:
    message = await run_tool_call(
        "call-2",
        "search_portfolio",
        json.dumps({"query": "Rust", "unexpected": True}),
        FakePortfolio(),
        "America/Argentina/Buenos_Aires",
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unexpected tool argument" in body["error"]["message"]


@pytest.mark.asyncio
async def test_tool_validation_rejects_wrong_integer_type() -> None:
    message = await run_tool_call(
        "call-3",
        "add_duration_to_datetime",
        json.dumps({"datetime": "2026-09-04", "days": "15"}),
        FakePortfolio(),
        "America/Argentina/Buenos_Aires",
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["message"] == "days must be an integer"
