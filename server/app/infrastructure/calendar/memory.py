from __future__ import annotations

from datetime import datetime, timezone

from app.domain.scheduling import BookingResult, BusyInterval, PendingBooking


class InMemoryCalendarGateway:
    def __init__(self, busy: list[BusyInterval] | None = None) -> None:
        self.busy = busy or []
        self.bookings: dict[str, BookingResult] = {}

    async def busy_intervals(
        self,
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> list[BusyInterval]:
        del timezone_name
        return [item for item in self.busy if item.start < end and item.end > start]

    async def create_booking(self, booking: PendingBooking, timezone_name: str) -> BookingResult:
        del timezone_name
        existing = self.bookings.get(booking.booking_id)
        if existing:
            return existing
        result = BookingResult(
            booking_id=booking.booking_id,
            event_id=f"mock-{booking.booking_id}",
            html_link=None,
            start=booking.slot.start.astimezone(timezone.utc),
            end=booking.slot.end.astimezone(timezone.utc),
        )
        self.bookings[booking.booking_id] = result
        return result
