from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, AsyncIterator
from zoneinfo import ZoneInfo

import pytest

from app.agent import BusinessRepresentative
from app.calendar_gateway import BookingResult, InMemoryCalendarGateway
from app.llama_client import ChatResult
from app.policies import SchedulingPolicy
from app.profile import BusinessProfile
from app.session import OfferedSlot, PendingBooking, SessionStore
from app.slot_service import SlotService


class FakeLlama:
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        del messages, tools
        return ChatResult(content="", tool_calls=[])

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        del messages
        yield "Confirmed. The meeting is on the calendar."


class CountingCalendar(InMemoryCalendarGateway):
    def __init__(self) -> None:
        super().__init__()
        self.create_calls = 0

    async def create_booking(self, booking: PendingBooking, timezone_name: str) -> BookingResult:
        self.create_calls += 1
        return await super().create_booking(booking, timezone_name)


@pytest.mark.asyncio
async def test_calendar_write_happens_only_after_explicit_confirmation(
    profile: BusinessProfile,
) -> None:
    sessions = SessionStore()
    policy = SchedulingPolicy(profile.scheduling)
    calendar = CountingCalendar()
    agent = BusinessRepresentative(
        profile,
        sessions,
        policy,
        SlotService(calendar, policy),
        calendar,
        FakeLlama(),  # type: ignore[arg-type]
    )
    state = await sessions.get("session-1234")
    tz = ZoneInfo(profile.scheduling.timezone)
    slot = OfferedSlot(
        start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
        end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
    )
    state.pending_booking = PendingBooking(
        booking_id="abc123",
        slot=slot,
        visitor_name="Ada Lovelace",
        visitor_email="ada@example.com",
        subject="Architecture discussion",
    )

    output = "".join(
        [chunk async for chunk in agent.respond("session-1234", "Tuesday could work")]
    )
    assert calendar.create_calls == 0
    assert state.pending_booking is not None
    assert output

    output = "".join(
        [chunk async for chunk in agent.respond("session-1234", "Sí, confirmo")]
    )
    assert calendar.create_calls == 1
    assert state.pending_booking is None
    assert "calendar" in output.lower()


@pytest.mark.asyncio
async def test_prepare_booking_only_accepts_previously_offered_slot(
    profile: BusinessProfile,
) -> None:
    sessions = SessionStore()
    policy = SchedulingPolicy(profile.scheduling)
    calendar = CountingCalendar()
    agent = BusinessRepresentative(
        profile,
        sessions,
        policy,
        SlotService(calendar, policy),
        calendar,
        FakeLlama(),  # type: ignore[arg-type]
    )
    state = await sessions.get("session-5678")
    tz = ZoneInfo(profile.scheduling.timezone)
    offered = OfferedSlot(
        start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
        end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
    )
    state.offered_slots = [offered]

    rejected = agent._prepare_booking(  # noqa: SLF001 - policy-level test
        state,
        {
            "slot_start": (offered.start + timedelta(hours=1)).isoformat(),
            "visitor_name": "Ada Lovelace",
            "visitor_email": "ada@example.com",
            "subject": "Architecture discussion",
        },
    )
    assert rejected["ok"] is False
    assert state.pending_booking is None

    accepted = agent._prepare_booking(  # noqa: SLF001 - policy-level test
        state,
        {
            "slot_start": offered.start.isoformat(),
            "visitor_name": "Ada Lovelace",
            "visitor_email": "ada@example.com",
            "subject": "Architecture discussion",
        },
    )
    assert accepted["ok"] is True
    assert accepted["status"] == "awaiting_explicit_confirmation"
    assert state.pending_booking is not None
