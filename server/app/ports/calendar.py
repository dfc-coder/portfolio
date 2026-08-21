from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.scheduling import BookingResult, BusyInterval, PendingBooking


class CalendarPort(Protocol):
    async def busy_intervals(
        self,
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> list[BusyInterval]: ...

    async def create_booking(
        self,
        booking: PendingBooking,
        timezone_name: str,
    ) -> BookingResult: ...
