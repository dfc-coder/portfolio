from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.pockettrace import PocketTraceRecorder


@pytest.mark.asyncio
async def test_pockettrace_recorder_posts_valid_snapshot_shape() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["host"] = request.headers.get("host")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        recorder = PocketTraceRecorder(
            "http://host.containers.internal:4319",
            "Qwen3.5-0.8B",
            client=client,
        )
        trace = recorder.start_turn("session-1", "che, ¿PocketTrace qué onda?")
        trace.add_attributes(route="business")
        trace.add_span(
            "profile_retrieval",
            12.4,
            input={"query": "PocketTrace"},
            output={
                "documents": [
                    {
                        "id": "projects.3",
                        "score": 0.94,
                        "content": "PocketTrace is a local-first trace inspector.",
                    }
                ]
            },
        )
        trace.finish(output={"response": "Es un inspector local de trazas."})

        await recorder.flush(trace)

    assert captured["host"] == "127.0.0.1:4319"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["schema_version"] == 1
    assert len(payload["traces"]) == 1
    assert len(payload["spans"]) == 1

    trace_payload = payload["traces"][0]
    assert trace_payload["app"] == "portfolio-representative"
    assert trace_payload["name"] == "chat_turn"
    assert trace_payload["status"] == "ok"
    assert trace_payload["attributes"]["session_id"] == "session-1"
    assert trace_payload["attributes"]["model"] == "Qwen3.5-0.8B"
    assert trace_payload["attributes"]["route"] == "business"

    span = payload["spans"][0]
    assert span["trace_id"] == trace_payload["id"]
    assert span["parent_span_id"] is None
    assert span["name"] == "profile_retrieval"
    assert span["output"]["documents"][0]["id"] == "projects.3"
    assert span["output"]["documents"][0]["score"] == 0.94


@pytest.mark.asyncio
async def test_pockettrace_failure_is_fail_open() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        recorder = PocketTraceRecorder(
            "http://host.containers.internal:4319",
            "Qwen3.5-0.8B",
            client=client,
        )
        trace = recorder.start_turn("session-2", "hola")
        trace.finish(output={"response": "hola"})

        # Observability failures must never escape into the conversational path.
        await recorder.flush(trace)
