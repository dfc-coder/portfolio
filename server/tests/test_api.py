from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest

from app.infrastructure.config.settings import Settings
from app.main import create_app


class FakeAgent:
    async def respond(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        assert session_id == "browser-session-123"
        assert user_message == "Hello"
        yield "Hello"
        yield " from server"


class WarmAgent(FakeAgent):
    def __init__(self) -> None:
        self.warm_calls = 0

    async def warm(self) -> None:
        self.warm_calls += 1


def test_settings() -> Settings:
    return Settings(
        profile_path=Path("unused.json"),
        llama_base_url="http://llama:8080",
        llama_model="test",
        llama_timeout_seconds=1,
        session_ttl_seconds=60,
        session_max_turns=4,
        allowed_origins=("http://localhost:5173",),
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
            json={
                "session_id": "browser-session-123",
                "message": "Hello",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: ready" in response.text
    assert '"text": "Hello"' in response.text
    assert '"text": " from server"' in response.text
    assert "event: done" in response.text
