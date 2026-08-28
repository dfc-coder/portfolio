from __future__ import annotations

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.scheduler import SchedulerReply
from app.domain.conversation import ActiveWorkflow
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy


class FalsePositiveRouter:
    async def route(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(domain=RouteDomain.SCHEDULING, relation=RouteRelation.CONTINUE, route_key="scheduling_continue", confidence=0.8, source="test")

    async def route_non_scheduling(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(domain=RouteDomain.BUSINESS, relation=RouteRelation.INTERRUPT, route_key="business_fallback", confidence=0.9, source="test")


class NotApplicableScheduler:
    async def handle(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        del state, user_message, relation
        return SchedulerReply(not_applicable=True)


class CapabilityAwareLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del config
        system = messages[0]["content"]
        assert "AGENT_CAPABILITIES:" in system
        assert "Check calendar availability." in system
        assert "Create a meeting after explicit confirmation." in system
        yield "Sí. Puedo usar las herramientas habilitadas para consultar disponibilidad y preparar reuniones."

    async def health(self) -> bool:
        return True


class FakeEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    async def embed_query(self, text, task):  # type: ignore[no-untyped-def]
        del text, task
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_false_scheduling_route_falls_back_to_business_and_preserves_workflow(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore()
    state = await sessions.get("session-tools")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"
    llm = CapabilityAwareLlm()
    responder = Responder(
        llm,
        profile,
        policy,
        GenerationConfig(temperature=0.65, max_tokens=180),
        ("Check calendar availability.", "Create a meeting after explicit confirmation."),
        FakeEmbeddings(),
    )
    agent = BusinessRepresentative(
        sessions,
        FalsePositiveRouter(),  # type: ignore[arg-type]
        NotApplicableScheduler(),  # type: ignore[arg-type]
        responder,
    )

    answer = "".join([chunk async for chunk in agent.respond("session-tools", "¿Tenés herramientas?")])
    state = await sessions.get("session-tools")

    assert "herramientas" in answer.lower()
    assert state.current_focus == RouteDomain.BUSINESS
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"
