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
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert function["parameters"]["additionalProperties"] is False


def test_add_duration_requires_timezone_and_calculates_exactly() -> None:
    result = add_duration_to_datetime(
        "2030-01-02T10:30:00-03:00",
        days=57,
        hours=2,
        minutes=15,
    )

    assert result == {"datetime": "2030-02-28T12:45:00-03:00"}

    with pytest.raises(ValueError, match="timezone"):
        add_duration_to_datetime("2030-01-02T10:30:00", days=1)


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
