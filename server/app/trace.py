from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_trace(message: str, context: list[dict[str, Any]], model: str) -> dict[str, Any]:
    return {
        "trace_id": str(uuid4()),
        "started_at": _utc_now(),
        "_started": time.perf_counter(),
        "status": "running",
        "input": {"message": message, "context": context},
        "model": {"name": model},
        "rounds": [],
        "final_ttft_ms": None,
        "output": None,
        "returned_context": None,
        "error": None,
    }


def start_round(trace: dict[str, Any] | None, number: int) -> dict[str, Any] | None:
    if trace is None:
        return None
    value = {
        "round": number,
        "response": {"finish_reason": None, "duration_ms": None},
        "tool_calls": [],
    }
    trace["rounds"].append(value)
    return value


def record_final_ttft(trace: dict[str, Any] | None) -> None:
    if trace is None or trace["final_ttft_ms"] is not None:
        return
    trace["final_ttft_ms"] = _elapsed_ms(trace["_started"])


def finish_round(
    round_trace: dict[str, Any] | None,
    finish_reason: str | None,
    started: float,
) -> None:
    if round_trace is None:
        return
    round_trace["response"]["finish_reason"] = finish_reason
    round_trace["response"]["duration_ms"] = _elapsed_ms(started)


def record_tool(
    round_trace: dict[str, Any] | None,
    call: dict[str, str],
    result: dict[str, object],
    started: float,
) -> None:
    if round_trace is None:
        return
    round_trace["tool_calls"].append(
        {
            "id": call["id"],
            "name": call["name"],
            "arguments_raw": call["arguments"],
            "arguments": _parse_json(call["arguments"]),
            "duration_ms": _elapsed_ms(started),
            "ok": bool(result.get("ok")),
            "result": result,
        }
    )


def finish_trace(
    trace: dict[str, Any],
    output: str | None,
    returned_context: list[dict[str, Any]] | None,
    error: dict[str, str] | None,
) -> dict[str, Any]:
    trace["status"] = "error" if error else "ok"
    trace["output"] = output
    trace["returned_context"] = returned_context
    trace["error"] = error
    trace["finished_at"] = _utc_now()
    trace["duration_ms"] = _elapsed_ms(trace.pop("_started"))
    return trace


def _parse_json(value: str) -> object | None:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
