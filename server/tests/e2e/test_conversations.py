from __future__ import annotations

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig


class FakeLlm:
    def __init__(self) -> None:
        self.stream_calls = 0

    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del config
        self.stream_calls += 1
        system = messages[0]["content"]
        assert "PORTFOLIO_KNOWLEDGE:" in system
        yield "Diego trabaja con arquitectura de "
        yield "integraciones y Applied AI."

    async def health(self) -> bool:
        return True


class BusinessEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0]
            if (
                "Professional experience." in text
                or "Professional skills" in text
                or "Portfolio project:" in text
            )
            else [0.0, 1.0]
            for text in texts
        ]

    async def embed_query(self, text: str) -> list[float]:
        del text
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


def build_agent(profile: BusinessProfile):
    llm = FakeLlm()
    sessions = MemorySessionStore()
    responder = Responder(
        llm,
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        BusinessEmbeddings(),
        knowledge_min_score=0.25,
    )
    return BusinessRepresentative(sessions, responder), sessions, llm


@pytest.mark.asyncio
async def test_multi_turn_portfolio_knowledge_conversation(
    profile: BusinessProfile,
) -> None:
    agent, sessions, llm = build_agent(profile)

    first = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-123",
                "¿En qué tecnologías trabaja Diego?",
            )
        ]
    )
    second = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-123",
                "¿Y qué experiencia profesional tiene?",
            )
        ]
    )

    state = await sessions.get("session-123")
    assert llm.stream_calls == 2
    assert "integraciones" in first.lower()
    assert "applied ai" in second.lower()
    assert state.current_focus == RouteDomain.BUSINESS
    assert len(state.turns) == 4
