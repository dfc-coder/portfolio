from __future__ import annotations

import pytest

from app.agent.belief import BeliefUpdater
from app.agent.context import ContextBuilder
from app.agent.renderer import HybridRenderer
from app.agent.representative import BusinessRepresentative
from app.agent.verifier import AgentVerifier
from app.domain.conversation import ActiveWorkflow
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.domain.semantics import DialogueAct, SchedulingCommand
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy


class FalsePositiveRouter:
    async def route(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(domain=RouteDomain.SCHEDULING, relation=RouteRelation.CONTINUE, route_key="scheduling_continue", confidence=0.8, source="test")

    async def route_non_scheduling(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(domain=RouteDomain.BUSINESS, relation=RouteRelation.INTERRUPT, route_key="business_fallback", confidence=0.9, source="test")


class NotApplicableInterpreter:
    async def interpret(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        del state, user_message, relation
        return SchedulingCommand(act=DialogueAct.NOT_APPLICABLE)


class NeverLoop:
    async def run(self, state, command, user_message):  # type: ignore[no-untyped-def]
        del state, command, user_message
        raise AssertionError("capability loop must not run for not_applicable")


class StreamingLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        yield "Sí. Diego trabaja con herramientas de integración y AI."

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_false_scheduling_route_falls_back_to_business_and_preserves_workflow(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore()
    state = await sessions.get("session-tools")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"
    llm = StreamingLlm()
    renderer = HybridRenderer(
        llm,
        ContextBuilder(profile, policy),
        GenerationConfig(temperature=0.65, max_tokens=180),
        GenerationConfig(temperature=0.1, max_tokens=96),
    )
    agent = BusinessRepresentative(
        sessions,
        policy,
        FalsePositiveRouter(),  # type: ignore[arg-type]
        NotApplicableInterpreter(),  # type: ignore[arg-type]
        BeliefUpdater(),
        NeverLoop(),  # type: ignore[arg-type]
        AgentVerifier(),
        renderer,
    )

    answer = "".join([chunk async for chunk in agent.respond("session-tools", "¿Tenés herramientas?")])
    state = await sessions.get("session-tools")

    assert "herramientas" in answer.lower()
    assert state.current_focus == RouteDomain.BUSINESS
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"
