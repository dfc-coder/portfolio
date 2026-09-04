import logging

import pytest

from app.agent import _validate_model_round


def test_finish_reason_tool_calls_requires_actual_calls() -> None:
    with pytest.raises(RuntimeError, match="returned no tool calls"):
        _validate_model_round("tool_calls", [])


def test_tool_calls_remain_authoritative_for_loop_control(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        _validate_model_round(
            "stop",
            [{"id": "call-1", "name": "search_portfolio", "arguments": "{}"}],
        )

    assert "unexpected finish_reason=stop" in caplog.text
