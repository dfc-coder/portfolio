from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.agent.belief import BeliefUpdater
from app.agent.capability_registry import CapabilityRegistry
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.domain.semantics import DialogueAct, SchedulingCommand


def names(items):  # type: ignore[no-untyped-def]
    return {item.name for item in items}


def test_dates_enable_calendar_read_without_conversation_stage() -> None:
    state = SessionState("s1")
    command = SchedulingCommand(act=DialogueAct.INFORM, start_date=date(2026, 8, 25))
    belief = BeliefUpdater()
    facts = belief.apply(state, command)

    eligible = CapabilityRegistry().eligible(RouteDomain.SCHEDULING, command, facts)

    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert "calendar.search_availability" in names(eligible)
    assert "scheduling.ask_dates" not in names(eligible)


def test_pending_booking_is_not_writable_without_explicit_confirmation_fact() -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    slot = OfferedSlot(
        start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
        end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
    )
    state = SessionState("s2")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.offered_slots = {"S1": slot}
    state.scheduling.selected_slot_id = "S1"
    state.scheduling.pending_booking = PendingBooking(
        booking_id="pending-1",
        slot=slot,
        visitor_name="Ana",
        visitor_email="ana@example.com",
        subject="Architecture",
    )
    command = SchedulingCommand(act=DialogueAct.CONFIRM)
    facts = BeliefUpdater.facts(state, command)

    eligible = CapabilityRegistry().eligible(RouteDomain.SCHEDULING, command, facts)

    assert "calendar.create_booking" not in names(eligible)
    assert "scheduling.confirmation_required" in names(eligible)


def test_details_while_waiting_for_slot_preserve_workflow_and_offer_slots_again() -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    state = SessionState("s3")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.requested_start_date = date(2026, 8, 25)
    state.scheduling.requested_end_date = date(2026, 8, 25)
    state.scheduling.offered_slots = {
        "S1": OfferedSlot(
            start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
        )
    }
    command = SchedulingCommand(act=DialogueAct.INFORM, visitor_email="ana@example.com")
    belief = BeliefUpdater()
    facts = belief.apply(state, command)

    eligible = CapabilityRegistry().eligible(RouteDomain.SCHEDULING, command, facts)

    assert state.scheduling.visitor_email == "ana@example.com"
    assert "scheduling.ask_slot" in names(eligible)
