from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from app.domain.capabilities import CapabilitySpec
from app.domain.conversation import SessionState
from app.domain.planning import Observation, ObservationType
from app.domain.scheduling import PendingBooking
from app.domain.semantics import SchedulingCommand
from app.ports.calendar import CalendarPort
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService

Handler = Callable[[SessionState, SchedulingCommand], Awaitable[Observation]]


class CapabilityExecutor:
    def __init__(
        self,
        slots: SlotService,
        calendar: CalendarPort,
        policy: SchedulingPolicy,
    ) -> None:
        self._slots = slots
        self._calendar = calendar
        self._policy = policy
        self._handlers: dict[str, Handler] = {
            "scheduling.cancel": self._cancel,
            "calendar.create_booking": self._create_booking,
            "scheduling.confirmation_required": self._confirmation_required,
            "scheduling.select_slot": self._select_slot,
            "calendar.search_availability": self._search_availability,
            "scheduling.prepare_booking": self._prepare_booking,
            "scheduling.ask_details": self._ask_details,
            "scheduling.ask_dates": self._ask_dates,
        }

    async def execute(
        self,
        capability: CapabilitySpec,
        state: SessionState,
        command: SchedulingCommand,
    ) -> Observation:
        handler = self._handlers.get(capability.name)
        if handler is None:
            return Observation(type=ObservationType.TOOL_ERROR, data={"error": "unknown_capability"})
        return await handler(state, command)

    async def _ask_dates(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del state, command
        return Observation(type=ObservationType.MISSING_FIELDS, data={"fields": ["date_range"]})

    async def _ask_details(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        return Observation(
            type=ObservationType.MISSING_FIELDS,
            data={"fields": state.scheduling.missing_details()},
        )

    async def _confirmation_required(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        pending = state.scheduling.pending_booking
        if pending is None:
            return Observation(type=ObservationType.TOOL_ERROR, data={"error": "missing_pending_booking"})
        return Observation(
            type=ObservationType.AWAITING_CONFIRMATION,
            data={
                "start": pending.slot.start.isoformat(),
                "end": pending.slot.end.isoformat(),
                "subject": pending.subject,
                "visitor_email": pending.visitor_email,
            },
        )

    async def _search_availability(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        memory = state.scheduling
        if memory.requested_start_date is None or memory.requested_end_date is None:
            return Observation(type=ObservationType.MISSING_FIELDS, data={"fields": ["date_range"]})
        try:
            slots = await self._slots.available_slots(memory.requested_start_date, memory.requested_end_date)
        except ValueError as exc:
            return Observation(type=ObservationType.TOOL_ERROR, data={"error": str(exc)})

        memory.offered_slots = {f"S{index}": slot for index, slot in enumerate(slots, start=1)}
        memory.selected_slot_id = None
        memory.pending_booking = None
        return Observation(
            type=ObservationType.AVAILABLE_SLOTS,
            data={
                "slots": [
                    {"id": slot_id, "start": slot.start.isoformat(), "end": slot.end.isoformat()}
                    for slot_id, slot in memory.offered_slots.items()
                ]
            },
        )

    async def _select_slot(self, state: SessionState, command: SchedulingCommand) -> Observation:
        memory = state.scheduling
        if not command.slot_id or command.slot_id not in memory.offered_slots:
            return Observation(type=ObservationType.INVALID_SLOT, data={"slot_id": command.slot_id})
        memory.selected_slot_id = command.slot_id
        memory.pending_booking = None
        return Observation(
            type=ObservationType.SUCCESS,
            data={"selected_slot_id": command.slot_id},
            requires_next_step=True,
        )

    async def _prepare_booking(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        memory = state.scheduling
        if memory.missing_details():
            return Observation(type=ObservationType.MISSING_FIELDS, data={"fields": memory.missing_details()})
        if not memory.selected_slot_id or memory.selected_slot_id not in memory.offered_slots:
            return Observation(type=ObservationType.INVALID_SLOT, data={"slot_id": memory.selected_slot_id})

        slot = memory.offered_slots[memory.selected_slot_id]
        pending = PendingBooking(
            booking_id=uuid.uuid4().hex,
            slot=slot,
            visitor_name=memory.visitor_name or "",
            visitor_email=memory.visitor_email or "",
            subject=memory.subject or "",
        )
        memory.pending_booking = pending
        return Observation(
            type=ObservationType.AWAITING_CONFIRMATION,
            data={
                "booking_id": pending.booking_id,
                "slot_id": memory.selected_slot_id,
                "start": pending.slot.start.isoformat(),
                "end": pending.slot.end.isoformat(),
                "visitor_name": pending.visitor_name,
                "visitor_email": pending.visitor_email,
                "subject": pending.subject,
            },
        )

    async def _create_booking(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        memory = state.scheduling
        pending = memory.pending_booking
        if pending is None:
            return Observation(type=ObservationType.TOOL_ERROR, data={"error": "missing_pending_booking"})
        try:
            result = await self._calendar.create_booking(pending, self._policy.config.timezone)
        except Exception:
            return Observation(type=ObservationType.TOOL_ERROR, data={"error": "calendar_write_failed"})

        state.last_booking_id = result.booking_id
        memory.pending_booking = None
        state.active_workflow = None
        return Observation(
            type=ObservationType.BOOKED,
            data={
                "start": pending.slot.start.isoformat(),
                "end": pending.slot.end.isoformat(),
                "subject": pending.subject,
                "visitor_email": pending.visitor_email,
            },
        )

    async def _cancel(self, state: SessionState, command: SchedulingCommand) -> Observation:
        del command
        state.reset_scheduling()
        return Observation(type=ObservationType.CANCELLED)
