from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum

from .routing import RouteDomain
from .scheduling import OfferedSlot, PendingBooking


class ActiveWorkflow(StrEnum):
    SCHEDULING = "scheduling"


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


@dataclass
class SchedulingMemory:
    """Facts known about the scheduling task; no conversational stage machine."""

    requested_start_date: date | None = None
    requested_end_date: date | None = None
    offered_slots: dict[str, OfferedSlot] = field(default_factory=dict)
    selected_slot_id: str | None = None
    visitor_name: str | None = None
    visitor_email: str | None = None
    subject: str | None = None
    pending_booking: PendingBooking | None = None

    def clear(self) -> None:
        self.requested_start_date = None
        self.requested_end_date = None
        self.offered_slots.clear()
        self.selected_slot_id = None
        self.visitor_name = None
        self.visitor_email = None
        self.subject = None
        self.pending_booking = None

    def missing_details(self) -> list[str]:
        missing: list[str] = []
        if not self.visitor_name:
            missing.append("visitor_name")
        if not self.visitor_email:
            missing.append("visitor_email")
        if not self.subject:
            missing.append("subject")
        return missing

    def facts(self) -> frozenset[str]:
        facts: set[str] = set()
        if self.requested_start_date and self.requested_end_date:
            facts.add("date_range")
        if self.offered_slots:
            facts.add("offered_slots")
        else:
            facts.add("no_offered_slots")
        if self.selected_slot_id:
            facts.add("selected_slot")
        if self.visitor_name:
            facts.add("visitor_name")
        if self.visitor_email:
            facts.add("visitor_email")
        if self.subject:
            facts.add("subject")
        if not self.missing_details():
            facts.add("details_complete")
        if self.pending_booking is not None:
            facts.add("pending_booking")
        return frozenset(facts)


@dataclass
class SessionState:
    session_id: str
    current_focus: RouteDomain = RouteDomain.BUSINESS
    active_workflow: ActiveWorkflow | None = None
    turns: list[ChatTurn] = field(default_factory=list)
    scheduling: SchedulingMemory = field(default_factory=SchedulingMemory)
    last_booking_id: str | None = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def reset_scheduling(self) -> None:
        self.current_focus = RouteDomain.BUSINESS
        self.active_workflow = None
        self.scheduling.clear()
