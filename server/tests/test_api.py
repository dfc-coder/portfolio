from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.infrastructure.config.settings import Settings
from app.main import create_app


class FakeAgent:
    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        assert session_id == "browser-session-123"
        assert user_message == "Hello"
        yield "Hello"
        yield " from server"


def test_sse_contract_streams_tokens() -> None:
    settings = Settings(
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
    app = create_app(settings, agent=FakeAgent())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/stream",
            json={"session_id": "browser-session-123", "message": "Hello"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: ready" in response.text
    assert '"text": "Hello"' in response.text
    assert '"text": " from server"' in response.text
    assert "event: done" in response.text
