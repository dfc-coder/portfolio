from __future__ import annotations

import copy
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
            "started_at": _utc_now(),
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
            "context": None,
            "error": None,
            "duration_ms": None,
        }

    def start_round(self, number: int, messages: list[dict[str, Any]]) -> dict[str, Any]:
        round_trace: dict[str, Any] = {
            "round": number,
            "request_messages": copy.deepcopy(messages),
            "response": {
                "id": None,
                "model": None,
                "created": None,
                "system_fingerprint": None,
                "finish_reason": None,
                "usage": None,
                "provider": {},
                "content": "",
                "chunk_count": 0,
                "first_delta_ms": None,
                "first_text_ms": None,
                "duration_ms": None,
            },
            "tool_calls": [],
            "_started": time.perf_counter(),
        }
        self.data["rounds"].append(round_trace)
        return round_trace

    def finish_round(self, round_trace: dict[str, Any]) -> None:
        started = float(round_trace.pop("_started"))
        round_trace["response"]["duration_ms"] = _elapsed_ms(started)

    def finish(
        self,
        *,
        status: str,
        output: str | None = None,
        context: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        self.data["status"] = status
        self.data["output"] = output
        self.data["context"] = copy.deepcopy(context)
        self.data["error"] = error
        self.data["finished_at"] = _utc_now()
        self.data["duration_ms"] = _elapsed_ms(self._started)
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


def parsed_json(value: str) -> object | None:
    import json

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
