from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.scheduler import Scheduler, SchedulingIntent, SchedulingTurn
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy


class QueueLlm:
    def __init__(self, turns: list[SchedulingTurn]) -> None:
        self.turns = turns

    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return self.turns.pop(0).model_dump_json()

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        if False:
            yield ""

    async def health(self) -> bool:
        return True


class FixedSlots:
    def __init__(self) -> None:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        self.slots = [
            OfferedSlot(
                start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
                end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
            )
        ]

    async def available_slots(self, start_date: date, end_date: date) -> list[OfferedSlot]:
        del start_date, end_date
        return self.slots


def make_scheduler(profile: BusinessProfile, turns: list[SchedulingTurn]) -> Scheduler:
    policy = SchedulingPolicy(profile.scheduling)
    return Scheduler(
        QueueLlm(turns),
        FixedSlots(),
        policy,
        GenerationConfig(temperature=0.0, max_tokens=64),
    )  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_date_input_reads_availability_without_stage_machine(profile: BusinessProfile) -> None:
    scheduler = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.INFORM, start_date=date(2026, 8, 25))],
    )
    state = SessionState("s1")
    reply = await scheduler.handle(state, "El 25 de agosto", RouteRelation.NEW)
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert "S1" in state.scheduling.offered_slots
    assert "S1" in reply.text


@pytest.mark.asyncio
async def test_non_explicit_confirmation_cannot_execute_calendar_command(
    profile: BusinessProfile,
) -> None:
    scheduler = make_scheduler(profile, [SchedulingTurn(intent=SchedulingIntent.CONFIRM)])
    state = SessionState("s2")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    slot = FixedSlots().slots[0]
    state.scheduling.offered_slots = {"S1": slot}
    state.scheduling.selected_slot_id = "S1"
    state.scheduling.pending_booking = PendingBooking(
        booking_id="pending",
        slot=slot,
        visitor_name="Ana",
        visitor_email="ana@example.com",
        subject="Architecture",
    )

    reply = await scheduler.handle(state, "Sí, confirmo", RouteRelation.CONTINUE)

    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.pending_booking is not None
    assert "confirmar reunión" in reply.text.lower()


@pytest.mark.asyncio
async def test_details_before_slot_are_preserved(profile: BusinessProfile) -> None:
    scheduler = make_scheduler(
        profile,
        [
            SchedulingTurn(
                intent=SchedulingIntent.INFORM,
                visitor_email="ana@example.com",
            )
        ],
    )
    state = SessionState("s4")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.requested_start_date = date(2026, 8, 25)
    state.scheduling.requested_end_date = date(2026, 8, 25)
    state.scheduling.offered_slots = {"S1": FixedSlots().slots[0]}

    reply = await scheduler.handle(
        state,
        "Mi email es ana@example.com",
        RouteRelation.CONTINUE,
    )

    assert state.scheduling.visitor_email == "ana@example.com"
    assert "S1" in reply.text


@pytest.mark.asyncio
async def test_unrecognized_scheduling_turn_returns_clarification_without_mutating_memory(
    profile: BusinessProfile,
) -> None:
    scheduler = make_scheduler(profile, [SchedulingTurn(intent=SchedulingIntent.OTHER)])
    state = SessionState("s5")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"

    reply = await scheduler.handle(
        state,
        "¿Podés usar herramientas?",
        RouteRelation.CONTINUE,
    )

    assert "agenda" in reply.text.lower()
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"
