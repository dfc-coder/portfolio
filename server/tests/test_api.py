from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import create_router


class FakeAgent:
    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        assert message == "hola"
        assert context == [{"role": "assistant", "content": "antes"}]
        yield "status", {"phase": "thinking", "round": 1}
        yield "tool", {"name": "get_current_datetime", "state": "running", "round": 1}
        yield "token", {"text": "respuesta"}
        yield "context", {
            "messages": [
                {"role": "assistant", "content": "antes"},
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "respuesta"},
            ]
        }


def test_chat_stream_contract() -> None:
    app = FastAPI()
    app.include_router(create_router(FakeAgent()))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/stream",
        json={
            "message": "hola",
            "context": [{"role": "assistant", "content": "antes"}],
        },
    )

    assert response.status_code == 200
    assert 'event: status' in response.text
    assert '"phase": "thinking"' in response.text
    assert 'event: tool' in response.text
    assert '"name": "get_current_datetime"' in response.text
    assert 'event: token' in response.text
    assert '"text": "respuesta"' in response.text
    assert 'event: context' in response.text
    assert '"role": "assistant"' in response.text
