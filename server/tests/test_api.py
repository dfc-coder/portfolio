from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import create_router


class FakeAgent:
    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        yield "respuesta"


def test_chat_stream_contract() -> None:
    app = FastAPI()
    app.include_router(create_router(FakeAgent()))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/stream",
        json={"session_id": "session-123", "message": "hola"},
    )

    assert response.status_code == 200
    assert "event: ready" in response.text
    assert '"text": "respuesta"' in response.text
    assert "event: done" in response.text
