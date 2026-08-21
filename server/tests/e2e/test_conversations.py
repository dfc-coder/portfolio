from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from app.agent.context import ContextBuilder
from app.agent.executor import ActionExecutor
from app.agent.fsm import ConversationFSM
from app.agent.planner import StructuredPlanner
from app.agent.renderer import HybridRenderer
from app.agent.representative import BusinessRepresentative
from app.agent.verifier import AgentVerifier
from app.domain.conversation import ConversationStage
from app.domain.planning import Plan
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.domain.scheduling import OfferedSlot
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy


class SequenceLlm:
    def __init__(self, plans: list[dict[str, Any]]) -> None:
        self._plans = plans
        self.stream_calls = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        del messages, config
        if response_schema is Plan:
            return json.dumps(self._plans.pop(0))
        raise AssertionError("Knowledge answers must use the streaming LLM path")

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        self.stream_calls += 1
        yield "Diego trabaja con arquitectura de "
        yield "integraciones, sistemas distribuidos "
        yield "y Applied AI."

    async def health(self) -> bool:
        return True


class SequenceRouter:
    def __init__(self, decisions: list[RoutingDecision]) -> None:
        self._decisions = decisions

    async def route(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return self._decisions.pop(0)


class FixedSlots:
    def __init__(self) -> None:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        self._slots = [
            OfferedSlot(
                start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
                end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
            ),
            OfferedSlot(
                start=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
                end=datetime(2026, 8, 25, 15, 0, tzinfo=tz),
            ),
        ]

    async def available_slots(self, start_date: date, end_date: date) -> list[OfferedSlot]:
        del start_date, end_date
        return self._slots


def build_agent(
    profile: BusinessProfile,
) -> tuple[BusinessRepresentative, MemorySessionStore, InMemoryCalendarGateway, SequenceLlm]:
    llm = SequenceLlm(
        [
            {
                "action": "get_availability",
                "start_date": "2026-08-25",
                "end_date": "2026-08-25",
            },
            {
                "action": "select_slot",
                "slot_id": "S2",
                "visitor_name": "Juan Perez",
                "visitor_email": "juan@example.com",
                "subject": "Architecture discussion",
            },
            {"action": "prepare_booking"},
        ]
    )
    router = SequenceRouter(
        [
            RoutingDecision(
                domain=RouteDomain.SCHEDULING,
                relation=RouteRelation.NEW,
                route_key="scheduling_new",
                confidence=0.95,
                source="test",
            ),
            RoutingDecision(
                domain=RouteDomain.BUSINESS,
                relation=RouteRelation.INTERRUPT,
                route_key="business_interrupt",
                confidence=0.95,
                source="test",
            ),
            RoutingDecision(
                domain=RouteDomain.SCHEDULING,
                relation=RouteRelation.CONTINUE,
                route_key="scheduling_continue",
                confidence=0.95,
                source="test",
            ),
        ]
    )
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore()
    calendar = InMemoryCalendarGateway()
    fsm = ConversationFSM()
    context = ContextBuilder(profile, policy)
    planner_cfg = GenerationConfig(temperature=0.15, max_tokens=96)
    repair_cfg = GenerationConfig(temperature=0.1, max_tokens=96)
    planner = StructuredPlanner(llm, context, fsm, planner_cfg, repair_cfg)
    renderer = HybridRenderer(
        llm,
        context,
        GenerationConfig(temperature=0.65, max_tokens=180),
        repair_cfg,
    )
    representative = BusinessRepresentative(
        sessions,
        policy,
        calendar,
        router,  # type: ignore[arg-type]
        planner,
        ActionExecutor(FixedSlots()),  # type: ignore[arg-type]
        fsm,
        AgentVerifier(fsm),
        renderer,
    )
    return representative, sessions, calendar, llm


@pytest.mark.asyncio
async def test_business_interrupt_preserves_scheduling_and_can_resume(profile: BusinessProfile) -> None:
    agent, sessions, calendar, llm = build_agent(profile)

    first = "".join(
        [chunk async for chunk in agent.respond("session-123", "Quiero una reunión el 25 de agosto")]
    )
    assert "S2" in first

    interrupted_chunks = [
        chunk
        async for chunk in agent.respond(
            "session-123",
            "Antes, ¿en qué tecnologías trabaja Diego?",
        )
    ]
    interrupted = "".join(interrupted_chunks)
    state = await sessions.get("session-123")
    assert len(interrupted_chunks) > 1
    assert llm.stream_calls == 1
    assert "integraciones" in interrupted.lower()
    assert state.stage == ConversationStage.SCHEDULING_SLOT
    assert "S2" in state.offered_slots
    assert state.active_workflow is not None

    second = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-123",
                "El segundo. Soy Juan Perez, juan@example.com, para hablar de arquitectura",
            )
        ]
    )
    state = await sessions.get("session-123")
    assert state.pending_booking is not None
    assert state.selected_slot_id == "S2"
    assert "confirmo" in second.lower()
    assert len(calendar.bookings) == 0

    third = "".join(
        [chunk async for chunk in agent.respond("session-123", "Sí, confirmo")]
    )
    state = await sessions.get("session-123")
    assert state.pending_booking is None
    assert state.active_workflow is None
    assert len(calendar.bookings) == 1
    assert "agendada" in third.lower()
