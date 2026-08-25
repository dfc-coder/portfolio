from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.domain.conversation import ActiveWorkflow
from app.domain.profile import BusinessProfile
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.sessions.memory import MemorySessionStore
from app.scheduling.approval import BookingAlreadyConfirmed, BookingApproval, BookingExpired, BookingNotPending
from app.scheduling.policy import SchedulingPolicy


async def prepare_pending(sessions: MemorySessionStore, session_id: str, *, booking_id: str = "booking-1", expires_at: datetime | None = None) -> PendingBooking:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    slot = OfferedSlot(start=datetime(2026, 8, 27, 14, 0, tzinfo=tz), end=datetime(2026, 8, 27, 14, 30, tzinfo=tz))
    pending = PendingBooking(booking_id=booking_id, slot=slot, visitor_name="Ana", visitor_email="ana@example.com", subject="Architecture", expires_at=expires_at)
    async with sessions.session(session_id) as state:
        state.active_workflow = ActiveWorkflow.SCHEDULING
        state.scheduling.offered_slots = {"S1": slot}
        state.scheduling.selected_slot_id = "S1"
        state.scheduling.pending_booking = pending
    return pending


@pytest.mark.asyncio
async def test_confirm_is_explicit_idempotent_calendar_boundary(profile: BusinessProfile) -> None:
    sessions = MemorySessionStore(); calendar = InMemoryCalendarGateway(); approval = BookingApproval(sessions, calendar, SchedulingPolicy(profile.scheduling))
    await prepare_pending(sessions, "session-approval", expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    first = await approval.confirm("session-approval", "booking-1")
    second = await approval.confirm("session-approval", "booking-1")
    assert first is not None
    assert second is None
    assert len(calendar.bookings) == 1
    state = await sessions.get("session-approval")
    assert state.last_booking_id == "booking-1"
    assert state.active_workflow is None
    assert state.scheduling.pending_booking is None


@pytest.mark.asyncio
async def test_confirm_rejects_booking_from_another_session(profile: BusinessProfile) -> None:
    sessions = MemorySessionStore(); calendar = InMemoryCalendarGateway(); approval = BookingApproval(sessions, calendar, SchedulingPolicy(profile.scheduling))
    await prepare_pending(sessions, "session-owner")
    with pytest.raises(BookingNotPending):
        await approval.confirm("session-other", "booking-1")
    assert len(calendar.bookings) == 0


@pytest.mark.asyncio
async def test_expired_booking_never_writes_calendar(profile: BusinessProfile) -> None:
    sessions = MemorySessionStore(); calendar = InMemoryCalendarGateway(); approval = BookingApproval(sessions, calendar, SchedulingPolicy(profile.scheduling))
    await prepare_pending(sessions, "session-expired", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(BookingExpired):
        await approval.confirm("session-expired", "booking-1")
    assert len(calendar.bookings) == 0
    state = await sessions.get("session-expired")
    assert state.scheduling.pending_booking is None


@pytest.mark.asyncio
async def test_cancel_clears_pending_without_calendar_write(profile: BusinessProfile) -> None:
    sessions = MemorySessionStore(); calendar = InMemoryCalendarGateway(); approval = BookingApproval(sessions, calendar, SchedulingPolicy(profile.scheduling))
    await prepare_pending(sessions, "session-cancel")
    await approval.cancel("session-cancel", "booking-1")
    assert len(calendar.bookings) == 0
    state = await sessions.get("session-cancel")
    assert state.active_workflow is None
    assert state.scheduling.pending_booking is None


@pytest.mark.asyncio
async def test_cancel_after_confirmation_is_rejected(profile: BusinessProfile) -> None:
    sessions = MemorySessionStore(); calendar = InMemoryCalendarGateway(); approval = BookingApproval(sessions, calendar, SchedulingPolicy(profile.scheduling))
    await prepare_pending(sessions, "session-confirmed")
    await approval.confirm("session-confirmed", "booking-1")
    with pytest.raises(BookingAlreadyConfirmed):
        await approval.cancel("session-confirmed", "booking-1")
