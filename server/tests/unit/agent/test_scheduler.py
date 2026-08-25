from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.scheduler import (
    Scheduler,
    SchedulerReplyKind,
    SchedulingIntent,
    SchedulingTurn,
)
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
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
                start=datetime(2026, 8, 26, 9, 0, tzinfo=tz),
                end=datetime(2026, 8, 26, 9, 30, tzinfo=tz),
            )
        ]

    async def available_slots(self, start_date: date, end_date: date) -> list[OfferedSlot]:
        del start_date, end_date
        return self.slots


def make_scheduler(profile: BusinessProfile, turns: list[SchedulingTurn]):
    policy = SchedulingPolicy(profile.scheduling)
    calendar = InMemoryCalendarGateway()
    scheduler = Scheduler(
        QueueLlm(turns),
        FixedSlots(),
        calendar,
        policy,
        GenerationConfig(temperature=0.0, max_tokens=64),
    )  # type: ignore[arg-type]
    return scheduler, calendar


@pytest.mark.asyncio
async def test_date_input_reads_availability_without_stage_machine(profile: BusinessProfile) -> None:
    scheduler, _ = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.INFORM, start_date=date(2026, 8, 26))],
    )
    state = SessionState("s1")
    reply = await scheduler.handle(state, "El 26 de agosto", RouteRelation.NEW)

    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert "S1" in state.scheduling.offered_slots
    assert reply.kind == SchedulerReplyKind.SLOTS
    assert reply.slots[0].slot_id == "S1"


@pytest.mark.asyncio
async def test_new_meeting_without_date_offers_next_available_slots(profile: BusinessProfile) -> None:
    scheduler, _ = make_scheduler(profile, [])
    state = SessionState("meeting")

    reply = await scheduler.handle(
        state,
        "Quiero una entrevista con Diego",
        RouteRelation.NEW,
    )

    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.requested_start_date is not None
    assert state.scheduling.requested_end_date is not None
    assert reply.kind == SchedulerReplyKind.SLOTS
    assert reply.slots[0].slot_id == "S1"


@pytest.mark.asyncio
async def test_non_explicit_confirmation_never_writes_calendar(profile: BusinessProfile) -> None:
    scheduler, calendar = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.CONFIRM)],
    )
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

    reply = await scheduler.handle(state, "Tuesday could work", RouteRelation.CONTINUE)

    assert len(calendar.bookings) == 0
    assert state.scheduling.pending_booking is None
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert reply.kind == SchedulerReplyKind.SLOTS


@pytest.mark.asyncio
async def test_text_confirmation_requires_hitl_and_never_writes_calendar(profile: BusinessProfile) -> None:
    scheduler, calendar = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.CONFIRM)],
    )
    state = SessionState("s3")
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

    assert len(calendar.bookings) == 0
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.pending_booking is not None
    assert reply.kind == SchedulerReplyKind.APPROVAL_REQUIRED
    assert reply.subject == "Architecture"


@pytest.mark.asyncio
async def test_details_before_slot_are_preserved(profile: BusinessProfile) -> None:
    scheduler, _ = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.INFORM, visitor_email="ana@example.com")],
    )
    state = SessionState("s4")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.requested_start_date = date(2026, 8, 26)
    state.scheduling.requested_end_date = date(2026, 8, 26)
    state.scheduling.offered_slots = {"S1": FixedSlots().slots[0]}

    reply = await scheduler.handle(
        state,
        "Mi email es ana@example.com",
        RouteRelation.CONTINUE,
    )

    assert state.scheduling.visitor_email == "ana@example.com"
    assert reply.kind == SchedulerReplyKind.SLOTS
    assert reply.slots[0].slot_id == "S1"


@pytest.mark.asyncio
async def test_professional_tool_question_escapes_false_scheduling_route(profile: BusinessProfile) -> None:
    scheduler, _ = make_scheduler(
        profile,
        [SchedulingTurn(intent=SchedulingIntent.OTHER)],
    )
    state = SessionState("s5")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"

    reply = await scheduler.handle(
        state,
        "¿Podés usar herramientas?",
        RouteRelation.CONTINUE,
    )

    assert reply.not_applicable is True
    assert reply.kind == SchedulerReplyKind.NOT_APPLICABLE
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"
