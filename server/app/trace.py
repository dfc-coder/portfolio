from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class TurnTrace:
    def __init__(
        self,
        *,
        message: str,
        context: list[dict[str, Any]],
        model: str,
        generation: dict[str, object],
        tools: list[dict[str, Any]],
    ) -> None:
        self._started = time.perf_counter()
        self.data: dict[str, Any] = {
            "trace_id": str(uuid4()),
            "started_at": utc_now(),
            "finished_at": None,
            "duration_ms": None,
            "status": "running",
            "input": {
                "message": message,
                "context": copy.deepcopy(context),
            },
            "model": {
                "name": model,
                "generation": copy.deepcopy(generation),
            },
            "tools": copy.deepcopy(tools),
            "rounds": [],
            "output": None,
            "returned_context": None,
            "error": None,
        }

    def start_round(self, number: int, messages: list[dict[str, Any]]) -> dict[str, Any]:
        round_trace: dict[str, Any] = {
            "round": number,
            "request_messages": copy.deepcopy(messages),
            "response": {
                "id": None,
                "object": None,
                "model": None,
                "created": None,
                "system_fingerprint": None,
                "finish_reason": None,
                "usage": None,
                "timings": None,
                "provider": {},
                "content": "",
                "chunk_count": 0,
                "first_delta_ms": None,
                "first_text_ms": None,
                "duration_ms": None,
            },
            "assistant_message": None,
            "tool_calls": [],
            "_started": time.perf_counter(),
        }
        self.data["rounds"].append(round_trace)
        return round_trace

    def finish_round(self, round_trace: dict[str, Any]) -> None:
        started = round_trace.pop("_started", None)
        if started is not None and round_trace["response"]["duration_ms"] is None:
            round_trace["response"]["duration_ms"] = elapsed_ms(float(started))

    def finish(
        self,
        *,
        status: str,
        output: str | None = None,
        context: list[dict[str, Any]] | None = None,
        error: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        for round_trace in self.data["rounds"]:
            self.finish_round(round_trace)

        self.data["status"] = status
        self.data["output"] = output
        self.data["returned_context"] = copy.deepcopy(context)
        self.data["error"] = copy.deepcopy(error)
        self.data["finished_at"] = utc_now()
        self.data["duration_ms"] = elapsed_ms(self._started)
        return copy.deepcopy(self.data)


def chunk_metadata(chunk: object) -> dict[str, Any]:
    model_dump = getattr(chunk, "model_dump", None)
    if not callable(model_dump):
        return {}

    payload = model_dump(exclude_none=True)
    if not isinstance(payload, dict):
        return {}
    payload.pop("choices", None)
    return payload


def parse_json(value: str) -> object | None:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
