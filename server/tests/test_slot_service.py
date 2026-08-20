from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.calendar_gateway import BusyInterval, InMemoryCalendarGateway
from app.policies import SchedulingPolicy
from app.profile import BusinessProfile
from app.slot_service import SlotService


@pytest.mark.asyncio
async def test_slots_respect_busy_time_and_buffer(profile: BusinessProfile) -> None:
    tz = ZoneInfo(profile.scheduling.timezone)
    calendar = InMemoryCalendarGateway(
        busy=[
            BusyInterval(
                start=datetime(2026, 8, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 8, 24, 10, 30, tzinfo=tz),
            )
        ]
    )
    service = SlotService(calendar, SchedulingPolicy(profile.scheduling))

    slots = await service.available_slots(
        date(2026, 8, 24),
        date(2026, 8, 24),
        now=datetime(2026, 8, 23, 8, 0, tzinfo=tz),
    )

    starts = [slot.start.strftime("%H:%M") for slot in slots]
    assert "09:00" in starts
    assert "09:30" not in starts
    assert "10:00" not in starts
    assert "10:30" not in starts
    assert "11:00" in starts
