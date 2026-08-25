from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.ports.calendar import CalendarPort
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService
from app.scheduling.turn_parser import SchedulingIntent, SchedulingTurn, SchedulingTurnParser

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_APPROVAL_TTL = timedelta(minutes=15)


class SchedulerReplyKind(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    CANCELLED = "cancelled"
    NEED_DATE = "need_date"
    INVALID_RANGE = "invalid_range"
    INVALID_SLOT = "invalid_slot"
    SLOTS = "slots"
    NO_SLOTS = "no_slots"
    MISSING_DETAILS = "missing_details"
    APPROVAL_REQUIRED = "approval_required"


class SlotOption(BaseModel):
    slot_id: str
    start: datetime
    end: datetime


class SchedulerReply(BaseModel):
    kind: SchedulerReplyKind = SchedulerReplyKind.NOT_APPLICABLE
    not_applicable: bool = False
    slots: list[SlotOption] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    subject: str | None = None
    start: datetime | None = None


class Scheduler:
    """Pure meeting workflow: interpret, update state, query slots, prepare booking."""

    PUBLIC_CAPABILITIES = (
        "Check Diego's calendar availability for a date or date range.",
        "Prepare a meeting from one of the offered time slots.",
        "Request explicit human approval before any meeting is created on the calendar.",
    )

    def __init__(
        self,
        llm: LlmPort,
        slots: SlotService,
        calendar: CalendarPort,
        policy: SchedulingPolicy,
        config: GenerationConfig,
    ) -> None:
        del calendar  # Calendar writes remain outside this service.
        self._slots = slots
        self._policy = policy
        self._parser = SchedulingTurnParser(llm, policy, config)

    @property
    def public_capabilities(self) -> tuple[str, ...]:
        return self.PUBLIC_CAPABILITIES

    async def handle(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
    ) -> SchedulerReply:
        memory = state.scheduling

        if (
            state.active_workflow == ActiveWorkflow.SCHEDULING
            and self._policy.is_rejection(user_message)
        ):
            state.reset_scheduling()
            return SchedulerReply(kind=SchedulerReplyKind.CANCELLED)

        turn = await self._parser.parse(state, user_message, relation)

        # NEW turns reach Scheduler only after operational admission. The parser may
        # still return OTHER when no date/details are present; admission is the authority
        # that this is a scheduling request, so treat it as REQUEST without duplicating
        # vocabulary here.
        if turn.intent == SchedulingIntent.OTHER and relation == RouteRelation.NEW:
            turn = SchedulingTurn(intent=SchedulingIntent.REQUEST)

        if turn.intent == SchedulingIntent.OTHER:
            return SchedulerReply(
                kind=SchedulerReplyKind.NOT_APPLICABLE,
                not_applicable=True,
            )
        if turn.intent == SchedulingIntent.CANCEL:
            state.reset_scheduling()
            return SchedulerReply(kind=SchedulerReplyKind.CANCELLED)

        state.active_workflow = ActiveWorkflow.SCHEDULING
        self._apply_turn(state, turn)

        if turn.intent == SchedulingIntent.CONFIRM and memory.pending_booking is not None:
            return self._approval_reply(memory.pending_booking)

        if turn.slot_id:
            if turn.slot_id not in memory.offered_slots:
                return SchedulerReply(
                    kind=SchedulerReplyKind.INVALID_SLOT,
                    slots=self._slot_options(memory.offered_slots),
                )
            memory.selected_slot_id = turn.slot_id
            memory.pending_booking = None

        if memory.requested_start_date is None or memory.requested_end_date is None:
            if turn.intent == SchedulingIntent.REQUEST:
                today = datetime.now(timezone.utc).astimezone(self._policy.timezone).date()
                memory.requested_start_date = today
                memory.requested_end_date = today + timedelta(
                    days=self._policy.config.max_days_ahead
                )
            else:
                return SchedulerReply(kind=SchedulerReplyKind.NEED_DATE)

        if not memory.offered_slots:
            try:
                slots = await self._slots.available_slots(
                    memory.requested_start_date,
                    memory.requested_end_date,
                )
            except ValueError:
                return SchedulerReply(kind=SchedulerReplyKind.INVALID_RANGE)

            memory.offered_slots = {
                f"S{index}": slot for index, slot in enumerate(slots, start=1)
            }
            memory.selected_slot_id = None
            memory.pending_booking = None
            return SchedulerReply(
                kind=(
                    SchedulerReplyKind.SLOTS
                    if memory.offered_slots
                    else SchedulerReplyKind.NO_SLOTS
                ),
                slots=self._slot_options(memory.offered_slots),
            )

        if memory.selected_slot_id is None:
            return SchedulerReply(
                kind=SchedulerReplyKind.SLOTS,
                slots=self._slot_options(memory.offered_slots),
            )

        missing = memory.missing_details()
        if memory.visitor_email and not _EMAIL_RE.fullmatch(memory.visitor_email.strip()):
            missing = [field for field in missing if field != "visitor_email"]
            missing.append("visitor_email")
        if missing:
            return SchedulerReply(
                kind=SchedulerReplyKind.MISSING_DETAILS,
                missing_fields=list(dict.fromkeys(missing)),
            )

        if memory.pending_booking is None:
            slot = memory.offered_slots.get(memory.selected_slot_id)
            if slot is None:
                memory.selected_slot_id = None
                return SchedulerReply(
                    kind=SchedulerReplyKind.SLOTS,
                    slots=self._slot_options(memory.offered_slots),
                )
            memory.pending_booking = PendingBooking(
                booking_id=uuid.uuid4().hex,
                slot=slot,
                visitor_name=memory.visitor_name or "",
                visitor_email=memory.visitor_email or "",
                subject=memory.subject or "",
                expires_at=datetime.now(timezone.utc) + _APPROVAL_TTL,
            )

        return self._approval_reply(memory.pending_booking)

    @staticmethod
    def _apply_turn(state: SessionState, turn: SchedulingTurn) -> None:
        memory = state.scheduling
        if turn.start_date is not None:
            changed = (
                memory.requested_start_date != turn.start_date
                or memory.requested_end_date != (turn.end_date or turn.start_date)
            )
            memory.requested_start_date = turn.start_date
            memory.requested_end_date = turn.end_date or turn.start_date
            if changed:
                memory.offered_slots.clear()
                memory.selected_slot_id = None
                memory.pending_booking = None
        if turn.visitor_name:
            memory.visitor_name = turn.visitor_name.strip()
        if turn.visitor_email:
            memory.visitor_email = turn.visitor_email.strip()
        if turn.subject:
            memory.subject = turn.subject.strip()

    @staticmethod
    def _slot_options(slots: dict[str, OfferedSlot]) -> list[SlotOption]:
        return [
            SlotOption(slot_id=slot_id, start=slot.start, end=slot.end)
            for slot_id, slot in slots.items()
        ]

    @staticmethod
    def _approval_reply(pending: PendingBooking) -> SchedulerReply:
        return SchedulerReply(
            kind=SchedulerReplyKind.APPROVAL_REQUIRED,
            subject=pending.subject,
            start=pending.slot.start,
        )


__all__ = [
    "Scheduler",
    "SchedulerReply",
    "SchedulerReplyKind",
    "SlotOption",
    "SchedulingIntent",
    "SchedulingTurn",
]
