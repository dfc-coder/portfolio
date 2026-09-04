from types import SimpleNamespace

import pytest

from app.agent import PortfolioAgent


class FakeEmbeddings:
    async def create(self, *, model: str, input: list[str]):
        data = []
        for index, text in enumerate(input):
            vector = [1.0, 0.0] if "Rust" in text or text.startswith("Instruct:") else [0.0, 1.0]
            data.append(SimpleNamespace(index=index, embedding=vector))
        return SimpleNamespace(data=data)


class FakeCompletions:
    def __init__(self) -> None:
        self.messages = []

    async def create(self, **kwargs):
        self.messages = kwargs["messages"]

        async def stream():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Incluye Rust."))]
            )

        return stream()


class FakeClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddings()
        self.chat = SimpleNamespace(completions=FakeCompletions())


@pytest.mark.asyncio
async def test_agent_retrieves_profile_and_streams_answer() -> None:
    profile = {
        "owner": {"name": "Diego"},
        "projects": [{"name": "PocketTrace", "stack": ["Rust"]}],
    }
    chat = FakeClient()
    embeddings = FakeClient()
    agent = PortfolioAgent(
        "Diego",
        profile,
        chat,
        embeddings,
        chat_model="qwen",
        embedding_model="qwen-embed",
        min_score=0.5,
    )

    response = "".join(
        [chunk async for chunk in agent.respond("¿Trabajó con Rust?", [])]
    )

    assert response == "Incluye Rust."
    assert "Rust" in chat.chat.completions.messages[0]["content"]
    assert chat.chat.completions.messages[-1]["content"] == "¿Trabajó con Rust?"
