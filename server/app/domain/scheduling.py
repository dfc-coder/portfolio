from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class OfferedSlot:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PendingBooking:
    booking_id: str
    slot: OfferedSlot
    visitor_name: str
    visitor_email: str
    subject: str


@dataclass(frozen=True)
class BookingResult:
    booking_id: str
    event_id: str
    html_link: str | None
    start: datetime
    end: datetime
