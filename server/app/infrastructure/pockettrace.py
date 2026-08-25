from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _duration_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _error_payload(exc: BaseException) -> dict[str, str]:
    return {
        "kind": type(exc).__name__,
        "message": str(exc)[:2000],
    }


def _without_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


@dataclass
class TraceSpan:
    span_id: str
    name: str
    duration_ms: int
    status: str = "ok"
    input: Any = None
    output: Any = None
    attributes: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def as_snapshot(self, trace_id: str) -> dict[str, Any]:
        return _without_none(
            {
                "id": self.span_id,
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": self.name,
                "duration_ms": self.duration_ms,
                "status": self.status,
                "input": self.input,
                "output": self.output,
                "attributes": self.attributes,
                "error": self.error,
            }
        )


@dataclass
class TurnTrace:
    trace_id: str
    app: str
    session_id: str
    model: str
    user_message: str
    started_at: float = field(default_factory=time.perf_counter)
    status: str = "running"
    output: Any = None
    error: dict[str, Any] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    spans: list[TraceSpan] = field(default_factory=list)

    def add_span(
        self,
        name: str,
        duration_ms: float,
        *,
        input: Any = None,
        output: Any = None,
        attributes: dict[str, Any] | None = None,
        status: str = "ok",
        error: dict[str, Any] | None = None,
    ) -> None:
        self.spans.append(
            TraceSpan(
                span_id=f"span_{uuid.uuid4().hex}",
                name=name,
                duration_ms=max(0, round(duration_ms)),
                status=status,
                input=input,
                output=output,
                attributes=attributes,
                error=error,
            )
        )

    def add_attributes(self, **attributes: Any) -> None:
        self.attributes.update(attributes)

    def finish(self, output: Any = None) -> None:
        if self.status != "running":
            return
        self.status = "ok"
        self.output = output

    def fail(self, exc: BaseException) -> None:
        self.status = "failed"
        self.error = _error_payload(exc)

    def snapshot(self) -> dict[str, Any]:
        trace = _without_none(
            {
                "id": self.trace_id,
                "app": self.app,
                "name": "chat_turn",
                "duration_ms": _duration_ms(self.started_at),
                "status": "ok" if self.status == "running" else self.status,
                "input": {"message": self.user_message},
                "output": self.output,
                "attributes": {
                    "session_id": self.session_id,
                    "model": self.model,
                    **self.attributes,
                },
                "error": self.error,
            }
        )
        return {
            "schema_version": 1,
            "traces": [trace],
            "spans": [span.as_snapshot(self.trace_id) for span in self.spans],
        }


class PocketTraceRecorder:
    """Fail-open exporter for PocketTrace's generic snapshot ingestion API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        app: str = "portfolio-representative",
        timeout_seconds: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._app = app
        self._timeout_seconds = timeout_seconds
        self._client = client

    def start_turn(self, session_id: str, user_message: str) -> TurnTrace:
        return TurnTrace(
            trace_id=f"trace_{uuid.uuid4().hex}",
            app=self._app,
            session_id=session_id,
            model=self._model,
            user_message=user_message,
        )

    async def flush(self, trace: TurnTrace) -> None:
        endpoint = f"{self._base_url}/api/snapshots"
        # PocketTrace is intentionally loopback-only and validates Host. When the
        # portfolio API runs in Podman, the transport URL may use
        # host.containers.internal while the HTTP Host must remain local.
        headers = {"Host": "127.0.0.1:4319"}
        try:
            if self._client is not None:
                response = await self._client.post(
                    endpoint,
                    json=trace.snapshot(),
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        endpoint,
                        json=trace.snapshot(),
                        headers=headers,
                    )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - observability must never break chat
            logger.warning("PocketTrace ingest failed: %s", exc)
