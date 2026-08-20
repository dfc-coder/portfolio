from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum

from .scheduling import OfferedSlot, PendingBooking


class ConversationStage(StrEnum):
    BUSINESS = "business"
    SCHEDULING_DATES = "scheduling_dates"
    SCHEDULING_SLOT = "scheduling_slot"
    SCHEDULING_DETAILS = "scheduling_details"
    SCHEDULING_CONFIRMATION = "scheduling_confirmation"
    COMPLETE = "complete"


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


@dataclass
class SessionState:
    session_id: str
    stage: ConversationStage = ConversationStage.BUSINESS
    turns: list[ChatTurn] = field(default_factory=list)
    requested_start_date: date | None = None
    requested_end_date: date | None = None
    offered_slots: dict[str, OfferedSlot] = field(default_factory=dict)
    selected_slot_id: str | None = None
    visitor_name: str | None = None
    visitor_email: str | None = None
    subject: str | None = None
    pending_booking: PendingBooking | None = None
    last_booking_id: str | None = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def reset_scheduling(self) -> None:
        self.stage = ConversationStage.BUSINESS
        self.requested_start_date = None
        self.requested_end_date = None
        self.offered_slots.clear()
        self.selected_slot_id = None
        self.visitor_name = None
        self.visitor_email = None
        self.subject = None
        self.pending_booking = None
