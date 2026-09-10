from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import create_router
from app.conversation import ConversationStore


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
        yield "tool", {"name": "resolve_datetime", "state": "running", "round": 1}
        yield "token", {"text": "res"}
        yield "token", {"text": "puesta"}
        yield "context", {
            "messages": [
                {"role": "assistant", "content": "antes"},
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "respuesta"},
            ]
        }
        if diagnostics:
            yield "trace", {"trace_id": "trace-1", "status": "ok"}


class SessionAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        self.calls.append((message, context))
        answer = "primera" if len(self.calls) == 1 else "segunda"
        updated = [
            *context,
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]
        yield "token", {"text": answer}
        yield "context", {"messages": updated}


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
    assert 'event: conversation' in response.text
    assert '"conversation_id":' in response.text
    assert 'event: status' in response.text
    assert '"phase": "model"' in response.text
    assert 'event: tool' in response.text
    assert '"name": "resolve_datetime"' in response.text
    assert response.text.count("event: token") == 2
    assert '"text": "res"' in response.text
    assert '"text": "puesta"' in response.text
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


def test_chat_reuses_server_context_by_conversation_id() -> None:
    app = FastAPI()
    agent = SessionAgent()
    app.include_router(create_router(agent, conversations=ConversationStore()))
    client = TestClient(app)

    first = client.post(
        "/v1/chat/stream",
        json={"message": "¿Diego usa Rust?", "context": []},
    )
    assert first.status_code == 200

    conversation_line = next(
        line
        for line in first.text.splitlines()
        if line.startswith("data: {\"conversation_id\"")
    )
    conversation_id = conversation_line.split('"')[3]

    second = client.post(
        "/v1/chat/stream",
        json={
            "message": "¿Y Go?",
            "conversation_id": conversation_id,
            "context": [],
        },
    )

    assert second.status_code == 200
    assert agent.calls[0] == ("¿Diego usa Rust?", [])
    assert agent.calls[1] == (
        "¿Y Go?",
        [
            {"role": "user", "content": "¿Diego usa Rust?"},
            {"role": "assistant", "content": "primera"},
        ],
    )


def test_chat_rejects_invalid_conversation_id() -> None:
    app = FastAPI()
    app.include_router(create_router(SessionAgent()))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/stream",
        json={"message": "hola", "conversation_id": "not-a-uuid"},
    )

    assert response.status_code == 422
