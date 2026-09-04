from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.scheduling import BookingResult, PendingBooking
from app.ports.sessions import SessionStorePort

from .calendar import Calendar
from .policy import SchedulingPolicy


class BookingApprovalError(RuntimeError):
    pass


class BookingNotPending(BookingApprovalError):
    pass


class BookingExpired(BookingApprovalError):
    pass


class BookingAlreadyConfirmed(BookingApprovalError):
    pass


@dataclass(frozen=True)
class BookingApprovalAction:
    booking_id: str
    subject: str
    visitor_name: str
    visitor_email: str
    start: datetime
    end: datetime
    expires_at: datetime | None


class BookingApproval:
    """Human approval boundary for calendar writes."""

    def __init__(
        self,
        sessions: SessionStorePort,
        calendar: Calendar,
        policy: SchedulingPolicy,
    ) -> None:
        self._sessions = sessions
        self._calendar = calendar
        self._policy = policy

    async def pending_action(self, session_id: str) -> BookingApprovalAction | None:
        async with self._sessions.session(session_id) as state:
            pending = state.scheduling.pending_booking
            if pending is None:
                return None
            if self._is_expired(pending):
                state.reset_scheduling()
                return None
            return self._to_action(pending)

    async def confirm(self, session_id: str, booking_id: str) -> BookingResult | None:
        async with self._sessions.session(session_id) as state:
            if state.last_booking_id == booking_id:
                return None

            pending = state.scheduling.pending_booking
            if pending is None or pending.booking_id != booking_id:
                raise BookingNotPending("Booking is not pending for this session.")
            if self._is_expired(pending):
                state.reset_scheduling()
                raise BookingExpired("Booking approval expired.")

            selected_slot_id = state.scheduling.selected_slot_id
            selected_slot = (
                state.scheduling.offered_slots.get(selected_slot_id)
                if selected_slot_id is not None
                else None
            )
            if selected_slot != pending.slot:
                raise BookingNotPending("Selected slot no longer matches the pending booking.")

            result = await self._calendar.create_booking(
                pending,
                self._policy.config.timezone,
            )
            state.last_booking_id = result.booking_id
            state.reset_scheduling()
            return result

    async def cancel(self, session_id: str, booking_id: str) -> None:
        async with self._sessions.session(session_id) as state:
            if state.last_booking_id == booking_id:
                raise BookingAlreadyConfirmed("Booking was already confirmed.")

            pending = state.scheduling.pending_booking
            if pending is None or pending.booking_id != booking_id:
                raise BookingNotPending("Booking is not pending for this session.")

            state.reset_scheduling()

    @staticmethod
    def _is_expired(pending: PendingBooking) -> bool:
        if pending.expires_at is None:
            return False
        return pending.expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def _to_action(pending: PendingBooking) -> BookingApprovalAction:
        return BookingApprovalAction(
            booking_id=pending.booking_id,
            subject=pending.subject,
            visitor_name=pending.visitor_name,
            visitor_email=pending.visitor_email,
            start=pending.slot.start,
            end=pending.slot.end,
            expires_at=pending.expires_at,
        )
