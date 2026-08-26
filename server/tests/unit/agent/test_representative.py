from __future__ import annotations

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig


class GroundedLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del config
        system = messages[0]["content"]
        if "PORTFOLIO_KNOWLEDGE:" in system:
            yield "Diego tiene experiencia en Applied AI e integraciones."
        else:
            yield "Hola. ¿En qué puedo ayudarte?"

    async def health(self) -> bool:
        return True


class ExperienceEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0]
            if "Professional experience." in text or "Experience area:" in text
            else [0.0, 1.0]
            for text in texts
        ]

    async def embed_query(self, text: str) -> list[float]:
        return [0.0, -1.0] if text.strip().lower() == "hola" else [1.0, 0.0]

    async def health(self) -> bool:
        return True


def build_agent(profile: BusinessProfile):
    sessions = MemorySessionStore()
    responder = Responder(
        GroundedLlm(),
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        ExperienceEmbeddings(),
        knowledge_min_score=0.25,
    )
    return BusinessRepresentative(sessions, responder), sessions


@pytest.mark.asyncio
async def test_business_question_uses_profile_retrieval(
    profile: BusinessProfile,
) -> None:
    agent, sessions = build_agent(profile)

    answer = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-experience",
                "Quiero información sobre la experiencia de Diego",
            )
        ]
    )
    state = await sessions.get("session-experience")

    assert "experiencia" in answer.lower()
    assert state.current_focus == RouteDomain.BUSINESS


@pytest.mark.asyncio
async def test_general_message_stays_outside_portfolio_knowledge(
    profile: BusinessProfile,
) -> None:
    agent, sessions = build_agent(profile)

    answer = "".join(
        [chunk async for chunk in agent.respond("session-general", "Hola")]
    )
    state = await sessions.get("session-general")

    assert "hola" in answer.lower()
    assert state.current_focus == RouteDomain.GENERAL
