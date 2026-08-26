from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest

from app.infrastructure.config.settings import Settings
from app.main import create_app


class FakeAgent:
    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        assert session_id == "browser-session-123"
        assert user_message == "Hello"
        yield "Hello"
        yield " from server"


class WarmAgent(FakeAgent):
    def __init__(self) -> None:
        self.warm_calls = 0

    async def warm(self) -> None:
        self.warm_calls += 1


class BlockingAgent:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        del session_id, user_message
        self.entered.set()
        await self.release.wait()
        yield "done"


def test_settings() -> Settings:
    return Settings(
        profile_path=Path("unused.json"),
        llama_base_url="http://llama:8080",
        llama_model="test",
        llama_timeout_seconds=1,
        session_ttl_seconds=60,
        session_max_turns=4,
        allowed_origins=("http://localhost:5173",),
        calendar_mode="mock",
        google_calendar_id="primary",
        google_client_id=None,
        google_client_secret=None,
        google_refresh_token=None,
    )


@pytest.mark.asyncio
async def test_lifespan_warms_semantic_indexes_before_serving() -> None:
    agent = WarmAgent()
    app = create_app(test_settings(), agent=agent)  # type: ignore[arg-type]

    assert agent.warm_calls == 0
    async with app.router.lifespan_context(app):
        assert agent.warm_calls == 1


@pytest.mark.asyncio
async def test_sse_contract_streams_tokens() -> None:
    app = create_app(test_settings(), agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/v1/chat/stream",
            json={"session_id": "browser-session-123", "message": "Hello"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: ready" in response.text
    assert '"text": "Hello"' in response.text
    assert '"text": " from server"' in response.text
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_public_api_docs_are_disabled_by_default() -> None:
    app = create_app(test_settings(), agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404


@pytest.mark.asyncio
async def test_public_edge_rejects_oversized_body() -> None:
    settings = replace(test_settings(), max_request_bytes=64)
    app = create_app(settings, agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/chat/stream",
            content=b"x" * 65,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "request_too_large"}


@pytest.mark.asyncio
async def test_public_edge_rate_limits_per_client() -> None:
    settings = replace(
        test_settings(),
        rate_limit_requests_per_window=1,
        global_rate_limit_requests_per_window=10,
    )
    app = create_app(settings, agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post(
            "/v1/chat/stream",
            json={"session_id": "browser-session-123", "message": "Hello"},
        )
        second = await client.post(
            "/v1/chat/stream",
            json={"session_id": "browser-session-123", "message": "Hello"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
    assert second.json() == {"detail": "client_rate_limit"}


@pytest.mark.asyncio
async def test_forwarded_ip_uses_rightmost_proxy_value() -> None:
    settings = replace(
        test_settings(),
        trust_proxy_headers=True,
        rate_limit_requests_per_window=1,
        global_rate_limit_requests_per_window=10,
    )
    app = create_app(settings, agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)
    payload = {"session_id": "browser-session-123", "message": "Hello"}

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post(
            "/v1/chat/stream",
            json=payload,
            headers={"X-Forwarded-For": "203.0.113.9, 198.51.100.7"},
        )
        same_client = await client.post(
            "/v1/chat/stream",
            json=payload,
            headers={"X-Forwarded-For": "192.0.2.4, 198.51.100.7"},
        )
        different_client = await client.post(
            "/v1/chat/stream",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.8"},
        )

    assert first.status_code == 200
    assert same_client.status_code == 429
    assert different_client.status_code == 200


@pytest.mark.asyncio
async def test_public_edge_limits_concurrent_streams() -> None:
    settings = replace(
        test_settings(),
        max_streams_per_client=1,
        max_global_streams=2,
        rate_limit_requests_per_window=10,
    )
    agent = BlockingAgent()
    app = create_app(settings, agent=agent)  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 12345))
    payload = {"session_id": "browser-session-123", "message": "Hello"}

    async with (
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as first_client,
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as second_client,
    ):
        first_task = asyncio.create_task(first_client.post("/v1/chat/stream", json=payload))
        await asyncio.wait_for(agent.entered.wait(), timeout=1.0)
        second = await second_client.post("/v1/chat/stream", json=payload)
        agent.release.set()
        first = await asyncio.wait_for(first_task, timeout=1.0)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "client_stream_limit"}


@pytest.mark.asyncio
async def test_security_headers_are_added() -> None:
    app = create_app(test_settings(), agent=FakeAgent())  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
