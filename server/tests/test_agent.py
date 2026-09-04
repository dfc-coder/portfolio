import pytest

from app.agent import PortfolioAgent
from app.llm import GenerationConfig
from app.search import Fact
from app.sessions import MemorySessions


class FakeSearch:
    async def warm(self) -> None:
        pass

    async def search(self, query: str) -> tuple[Fact, ...]:
        return (Fact(source="skills", text='{"programming_languages":["Rust"]}'),)


class FakeLlm:
    async def stream(self, messages, config):
        assert "Rust" in messages[0]["content"]
        yield "El perfil incluye experiencia con Rust."


@pytest.mark.asyncio
async def test_agent_retrieves_answers_and_keeps_history() -> None:
    sessions = MemorySessions(max_turns=8)
    agent = PortfolioAgent(
        "Diego",
        sessions,
        FakeSearch(),
        FakeLlm(),
        GenerationConfig(),
    )

    response = "".join(
        [chunk async for chunk in agent.respond("session-123", "¿Trabajó con Rust?")]
    )

    assert response == "El perfil incluye experiencia con Rust."
    async with sessions.open("session-123") as session:
        assert [turn.role for turn in session.turns] == ["user", "assistant"]
