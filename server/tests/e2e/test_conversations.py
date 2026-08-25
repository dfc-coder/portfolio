from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.scheduler import Scheduler, SchedulingIntent, SchedulingTurn
from app.domain.conversation import ActiveWorkflow
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.domain.scheduling import OfferedSlot
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.approval import BookingApproval
from app.scheduling.policy import SchedulingPolicy


class FakeLlm:
    def __init__(self) -> None:
        self.stream_calls = 0

    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return SchedulingTurn(intent=SchedulingIntent.OTHER).model_dump_json()

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
            if "skills" in text or "professional_experience" in text
            else [0.0, 1.0]
            for text in texts
        ]

    async def embed_query(self, text: str) -> list[float]:
        del text
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


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

    async def available_slots(
        self,
        start_date: date,
        end_date: date,
    ) -> list[OfferedSlot]:
        del start_date, end_date
        return self._slots


def build_agent(profile: BusinessProfile):
    llm = FakeLlm()
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore()
    calendar = InMemoryCalendarGateway()
    scheduler = Scheduler(
        llm,
        FixedSlots(),
        calendar,
        policy,
        GenerationConfig(temperature=0.0, max_tokens=64),
    )  # type: ignore[arg-type]
    responder = Responder(
        llm,
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        scheduler.public_capabilities,
        BusinessEmbeddings(),
        knowledge_min_score=0.50,
    )
    agent = BusinessRepresentative(sessions, scheduler, responder)
    approvals = BookingApproval(sessions, calendar, policy)
    return agent, sessions, calendar, llm, approvals


@pytest.mark.asyncio
async def test_scheduling_can_be_interrupted_by_retrieved_business_knowledge_and_resume(
    profile: BusinessProfile,
) -> None:
    agent, sessions, calendar, llm, approvals = build_agent(profile)

    first = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-123",
                "Quiero una reunión el 25 de agosto",
            )
        ]
    )
    assert "S2" in first

    interrupted = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-123",
                "Antes, ¿en qué tecnologías trabaja Diego?",
            )
        ]
    )
    state = await sessions.get("session-123")
    assert llm.stream_calls == 1
    assert "integraciones" in interrupted.lower()
    assert state.current_focus == RouteDomain.BUSINESS
    assert "S2" in state.scheduling.offered_slots
    assert state.active_workflow == ActiveWorkflow.SCHEDULING

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
    pending = state.scheduling.pending_booking
    assert pending is not None
    assert state.scheduling.selected_slot_id == "S2"
    assert "confirmar reunión" in second.lower()
    assert len(calendar.bookings) == 0

    result = await approvals.confirm("session-123", pending.booking_id)
    assert result is not None
    state = await sessions.get("session-123")
    assert state.scheduling.pending_booking is None
    assert state.active_workflow is None
    assert len(calendar.bookings) == 1


@pytest.mark.asyncio
async def test_date_without_meeting_intent_does_not_start_scheduling(
    profile: BusinessProfile,
) -> None:
    agent, sessions, calendar, _, _ = build_agent(profile)

    "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-date",
                "El 25 de agosto",
            )
        ]
    )
    state = await sessions.get("session-date")

    assert state.active_workflow is None
    assert len(calendar.bookings) == 0
