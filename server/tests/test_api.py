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
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        assert message == "hola"
        assert context == [{"role": "assistant", "content": "antes"}]
        yield "status", {"phase": "model", "round": 1}
        yield "tool", {"name": "get_current_datetime", "state": "running", "round": 1}
        yield "token", {"text": "respuesta"}
        yield "context", {
            "messages": [
                {"role": "assistant", "content": "antes"},
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "respuesta"},
            ]
        }
        if diagnostics:
            yield "trace", {"trace_id": "trace-1", "status": "ok"}


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
    assert '"phase": "model"' in response.text
    assert 'event: tool' in response.text
    assert '"name": "get_current_datetime"' in response.text
    assert 'event: token' in response.text
    assert '"text": "respuesta"' in response.text
    assert 'event: context' in response.text
    assert '"role": "assistant"' in response.text
    assert 'event: trace' not in response.text


def test_chat_trace_requires_matching_token() -> None:
    app = FastAPI()
    app.include_router(create_router(FakeAgent(), diagnostics_token="local-secret"))
    client = TestClient(app)
    payload = {
        "message": "hola",
        "context": [{"role": "assistant", "content": "antes"}],
    }

    denied = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"x-agent-diagnostics-token": "wrong"},
    )
    allowed = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"x-agent-diagnostics-token": "local-secret"},
    )

    assert 'event: trace' not in denied.text
    assert 'event: trace' in allowed.text
    assert '"trace_id": "trace-1"' in allowed.text
