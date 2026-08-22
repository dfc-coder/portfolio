from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.scheduler import Scheduler, SchedulingIntent, SchedulingTurn
from app.domain.conversation import ActiveWorkflow
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.domain.scheduling import OfferedSlot
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy


class TestLlm:
    def __init__(self, scheduling_turns: list[SchedulingTurn]) -> None:
        self._scheduling_turns = scheduling_turns
        self.stream_calls = 0

    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return self._scheduling_turns.pop(0).model_dump_json()

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        self.stream_calls += 1
        yield "Diego trabaja con arquitectura de "
        yield "integraciones y Applied AI."

    async def health(self) -> bool:
        return True


class SequenceRouter:
    def __init__(self, decisions: list[RoutingDecision]) -> None:
        self._decisions = decisions

    async def route(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return self._decisions.pop(0)

    async def route_non_scheduling(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(domain=RouteDomain.BUSINESS, relation=RouteRelation.INTERRUPT, route_key="business_fallback", confidence=1.0, source="test")


class FixedSlots:
    def __init__(self) -> None:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        self._slots = [
            OfferedSlot(start=datetime(2026, 8, 25, 14, 0, tzinfo=tz), end=datetime(2026, 8, 25, 14, 30, tzinfo=tz)),
            OfferedSlot(start=datetime(2026, 8, 25, 14, 30, tzinfo=tz), end=datetime(2026, 8, 25, 15, 0, tzinfo=tz)),
        ]

    async def available_slots(self, start_date: date, end_date: date) -> list[OfferedSlot]:
        del start_date, end_date
        return self._slots


def build_agent(profile: BusinessProfile):
    llm = TestLlm(
        [
            SchedulingTurn(intent=SchedulingIntent.INFORM, start_date=date(2026, 8, 25), end_date=date(2026, 8, 25)),
            SchedulingTurn(intent=SchedulingIntent.SELECT, slot_id="S2", visitor_name="Juan Perez", visitor_email="juan@example.com", subject="Architecture discussion"),
        ]
    )
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore()
    calendar = InMemoryCalendarGateway()
    scheduler = Scheduler(
        llm,
        FixedSlots(),  # type: ignore[arg-type]
        calendar,
        policy,
        GenerationConfig(temperature=0.1, max_tokens=96),
    )
    responder = Responder(
        llm,
        profile,
        policy,
        GenerationConfig(temperature=0.65, max_tokens=180),
        scheduler.public_capabilities,
    )
    router = SequenceRouter(
        [
            RoutingDecision(domain=RouteDomain.SCHEDULING, relation=RouteRelation.NEW, route_key="scheduling", confidence=1.0, source="test"),
            RoutingDecision(domain=RouteDomain.BUSINESS, relation=RouteRelation.INTERRUPT, route_key="business_interrupt", confidence=1.0, source="test"),
            RoutingDecision(domain=RouteDomain.SCHEDULING, relation=RouteRelation.CONTINUE, route_key="scheduling_continue", confidence=1.0, source="test"),
            RoutingDecision(domain=RouteDomain.SCHEDULING, relation=RouteRelation.CONTINUE, route_key="scheduling_continue", confidence=1.0, source="test"),
        ]
    )
    agent = BusinessRepresentative(sessions, router, scheduler, responder)  # type: ignore[arg-type]
    return agent, sessions, calendar, llm


@pytest.mark.asyncio
async def test_business_interrupt_preserves_scheduling_and_can_resume(profile: BusinessProfile) -> None:
    agent, sessions, calendar, llm = build_agent(profile)

    first = "".join([chunk async for chunk in agent.respond("session-123", "Quiero una reunión el 25 de agosto")])
    assert "S2" in first

    interrupted = "".join([chunk async for chunk in agent.respond("session-123", "Antes, ¿en qué tecnologías trabaja Diego?")])
    state = await sessions.get("session-123")
    assert llm.stream_calls == 1
    assert "integraciones" in interrupted.lower()
    assert "S2" in state.scheduling.offered_slots
    assert state.active_workflow == ActiveWorkflow.SCHEDULING

    second = "".join([chunk async for chunk in agent.respond("session-123", "El segundo. Soy Juan Perez, juan@example.com, para hablar de arquitectura")])
    state = await sessions.get("session-123")
    assert state.scheduling.pending_booking is not None
    assert state.scheduling.selected_slot_id == "S2"
    assert "confirmo" in second.lower()
    assert len(calendar.bookings) == 0

    third = "".join([chunk async for chunk in agent.respond("session-123", "Sí, confirmo")])
    state = await sessions.get("session-123")
    assert state.scheduling.pending_booking is None
    assert state.active_workflow is None
    assert len(calendar.bookings) == 1
    assert "agendada" in third.lower()
