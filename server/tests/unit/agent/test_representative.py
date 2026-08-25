from __future__ import annotations

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.scheduler import SchedulerReply
from app.domain.conversation import ActiveWorkflow
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig


class NotApplicableScheduler:
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        del state, user_message, relation
        self.calls += 1
        return SchedulerReply(not_applicable=True)


class AvailableScheduler:
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        del user_message, relation
        self.calls += 1
        state.active_workflow = ActiveWorkflow.SCHEDULING
        return SchedulerReply(
            text=(
                "Estos son los próximos horarios disponibles:\n"
                "- S1: miércoles 26/08 a las 09:00\n"
                "- S2: miércoles 26/08 a las 09:30"
            )
        )


class GroundedLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del config
        system = messages[0]["content"]
        assert "PORTFOLIO_KNOWLEDGE:" in system
        yield "Diego tiene experiencia en Applied AI e integraciones."

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
        del text
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_business_question_uses_profile_retrieval_without_intent_router(
    profile: BusinessProfile,
) -> None:
    sessions = MemorySessionStore()
    scheduler = NotApplicableScheduler()
    responder = Responder(
        GroundedLlm(),
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        ("Check calendar availability.",),
        ExperienceEmbeddings(),
        knowledge_min_score=0.25,
    )
    agent = BusinessRepresentative(
        sessions,
        scheduler,  # type: ignore[arg-type]
        responder,
    )

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

    assert scheduler.calls == 0
    assert "experiencia" in answer.lower()
    assert state.current_focus == RouteDomain.BUSINESS
    assert state.active_workflow is None


@pytest.mark.asyncio
async def test_bare_availability_question_returns_slots_from_scheduler(
    profile: BusinessProfile,
) -> None:
    sessions = MemorySessionStore()
    scheduler = AvailableScheduler()
    responder = Responder(
        GroundedLlm(),
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        (),
        ExperienceEmbeddings(),
        knowledge_min_score=0.25,
    )
    agent = BusinessRepresentative(
        sessions,
        scheduler,  # type: ignore[arg-type]
        responder,
    )

    answer = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-availability",
                "sobre tu disponibilidad?",
            )
        ]
    )
    state = await sessions.get("session-availability")

    assert scheduler.calls == 1
    assert "próximos horarios disponibles" in answer
    assert "S1" in answer
    assert state.current_focus == RouteDomain.SCHEDULING
    assert state.active_workflow == ActiveWorkflow.SCHEDULING


@pytest.mark.asyncio
async def test_business_interrupt_preserves_active_scheduling_state(
    profile: BusinessProfile,
) -> None:
    sessions = MemorySessionStore()
    state = await sessions.get("session-active")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"

    scheduler = NotApplicableScheduler()
    responder = Responder(
        GroundedLlm(),
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        (),
        ExperienceEmbeddings(),
        knowledge_min_score=0.25,
    )
    agent = BusinessRepresentative(
        sessions,
        scheduler,  # type: ignore[arg-type]
        responder,
    )

    "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-active",
                "Antes, contame sobre la experiencia de Diego",
            )
        ]
    )
    state = await sessions.get("session-active")

    assert scheduler.calls == 1
    assert state.current_focus == RouteDomain.BUSINESS
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"
