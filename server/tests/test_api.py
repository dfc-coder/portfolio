from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import create_router


class FakeAgent:
    async def respond(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        assert message == "hola"
        assert history == [{"role": "user", "content": "antes"}]
        yield "respuesta"


def test_chat_stream_contract() -> None:
    app = FastAPI()
    app.include_router(create_router(FakeAgent()))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/stream",
        json={
            "message": "hola",
            "history": [{"role": "user", "content": "antes"}],
        },
    )

    assert response.status_code == 200
    assert 'event: token' in response.text
    assert '"text": "respuesta"' in response.text
