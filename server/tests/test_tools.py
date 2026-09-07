import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from app.tools import (
    TOOLS,
    get_datetime_from_now,
    get_weekday_for_explicit_date,
    run_tool_call,
    set_relative_reminder_mock,
    shift_datetime,
)


class FakePortfolio:
    async def search(self, query: str):
        return [{"source": "projects.0", "text": f"fact for {query}"}]


def test_tool_schemas_are_explicit_json_schema() -> None:
    names = [tool["function"]["name"] for tool in TOOLS]

    assert names == [
        "search_portfolio",
        "get_current_datetime",
        "get_datetime_from_now",
        "shift_datetime",
        "get_weekday_for_explicit_date",
        "set_reminder_mock",
        "set_relative_reminder_mock",
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
    assert TOOLS[2]["function"]["parameters"]["required"] == ["offset", "unit"]
    assert TOOLS[3]["function"]["parameters"]["required"] == ["datetime", "offset", "unit"]
    assert TOOLS[4]["function"]["parameters"]["required"] == ["date"]
    assert TOOLS[5]["function"]["parameters"]["required"] == ["datetime", "message"]
    assert TOOLS[6]["function"]["parameters"]["required"] == ["message", "offset", "unit"]

    for index in (2, 3, 6):
        properties = TOOLS[index]["function"]["parameters"]["properties"]
        assert properties["unit"]["enum"] == ["minutes", "hours", "days", "weeks"]
        assert "minimum" not in properties["offset"]
        assert "maximum" not in properties["offset"]

    assert "2026-" not in json.dumps(TOOLS, ensure_ascii=False)


def test_shift_datetime_moves_forward_and_backward_exactly() -> None:
    forward = shift_datetime(
        "2026-09-04",
        days=15,
        default_timezone="America/Argentina/Buenos_Aires",
    )
    backward = shift_datetime(
        "2026-09-04",
        days=-1,
        default_timezone="America/Argentina/Buenos_Aires",
    )

    assert forward["date"] == "2026-09-19"
    assert forward["weekday"] == "Saturday"
    assert forward["weekday_es"] == "sábado"
    assert forward["iso_weekday"] == 6
    assert backward["date"] == "2026-09-03"


def test_shift_datetime_accepts_naive_datetime_in_default_timezone() -> None:
    result = shift_datetime(
        "2030-01-02T10:30:00",
        days=57,
        hours=2,
        minutes=15,
        default_timezone="America/Argentina/Buenos_Aires",
    )

    assert result["datetime"] == "2030-02-28T12:45:00-03:00"


def test_get_datetime_from_now_uses_current_time() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(days=1)

    result = get_datetime_from_now(
        days=1,
        timezone="America/Argentina/Buenos_Aires",
    )

    after = dt.datetime.now(zone) + dt.timedelta(days=1)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)
    assert result["timezone"] == "America/Argentina/Buenos_Aires"


def test_get_datetime_from_now_supports_weeks_without_model_conversion() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(weeks=1)

    result = get_datetime_from_now(
        weeks=1,
        timezone="America/Argentina/Buenos_Aires",
    )

    after = dt.datetime.now(zone) + dt.timedelta(weeks=1)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)


def test_get_weekday_for_explicit_date_has_no_relative_arithmetic() -> None:
    result = get_weekday_for_explicit_date(
        "2026-12-25",
        default_timezone="America/Argentina/Buenos_Aires",
    )

    assert result["date"] == "2026-12-25"
    assert result["weekday"] == "Friday"
    assert result["weekday_es"] == "viernes"
    assert result["iso_weekday"] == 5


def test_relative_reminder_resolves_target_from_now() -> None:
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    before = dt.datetime.now(zone) + dt.timedelta(hours=2)

    result = set_relative_reminder_mock(
        "Enviar el CV",
        hours=2,
        timezone="America/Argentina/Buenos_Aires",
    )

    after = dt.datetime.now(zone) + dt.timedelta(hours=2)
    actual = dt.datetime.fromisoformat(str(result["datetime"]))
    assert before.replace(microsecond=0) <= actual <= after.replace(microsecond=0)
    assert result["message"] == "Enviar el CV"
    assert result["persisted"] is False
    assert result["will_notify"] is False


def test_from_now_capability_requires_an_offset() -> None:
    with pytest.raises(ValueError, match="non-zero time offset"):
        get_datetime_from_now()


def test_shift_datetime_can_resolve_an_explicit_base_without_moving_it() -> None:
    result = shift_datetime(
        "2026-09-04",
        default_timezone="America/Argentina/Buenos_Aires",
    )

    assert result["date"] == "2026-09-04"
    assert result["weekday_es"] == "viernes"


def test_date_capability_owns_server_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "UTC")

    result = shift_datetime("2026-09-04", days=1)

    assert result["datetime"] == "2026-09-05T00:00:00+00:00"
    assert result["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_model_from_now_contract_preserves_request_unit() -> None:
    message = await run_tool_call(
        "call-relative",
        "get_datetime_from_now",
        json.dumps({"offset": 1, "unit": "weeks"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is True
    target = dt.datetime.fromisoformat(body["result"]["datetime"])
    now = dt.datetime.now(target.tzinfo)
    assert dt.timedelta(days=6, hours=23) < target - now < dt.timedelta(days=7, minutes=1)


@pytest.mark.asyncio
async def test_tool_validation_error_is_returned_to_model() -> None:
    message = await run_tool_call(
        "call-1",
        "shift_datetime",
        json.dumps({"datetime": "not-a-date", "offset": 2, "unit": "days"}),
        FakePortfolio(),
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
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unexpected tool argument" in body["error"]["message"]


@pytest.mark.asyncio
async def test_tool_validation_rejects_wrong_integer_type() -> None:
    message = await run_tool_call(
        "call-3",
        "get_datetime_from_now",
        json.dumps({"offset": "15", "unit": "days"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["message"] == "offset must be an integer"


@pytest.mark.asyncio
async def test_tool_validation_rejects_unknown_unit() -> None:
    message = await run_tool_call(
        "call-4",
        "set_relative_reminder_mock",
        json.dumps({"message": "Enviar CV", "offset": 2, "unit": "fortnights"}),
        FakePortfolio(),
    )

    body = json.loads(message["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "validation_error"
    assert "unit must be one of" in body["error"]["message"]
