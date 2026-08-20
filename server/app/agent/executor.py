from __future__ import annotations

import uuid

from app.domain.conversation import SessionState
from app.domain.planning import AgentAction, Observation, ObservationType, Plan
from app.domain.scheduling import PendingBooking
from app.scheduling.slots import SlotService


class ActionExecutor:
    def __init__(self, slots: SlotService) -> None:
        self._slots = slots

    async def execute(self, state: SessionState, plan: Plan) -> Observation:
        if plan.action == AgentAction.ASK_FOR_DATES:
            self._merge_details(state, plan)
            return Observation(
                type=ObservationType.MISSING_FIELDS,
                data={"fields": ["date_range"]},
            )
        if plan.action == AgentAction.GET_AVAILABILITY:
            return await self._get_availability(state, plan)
        if plan.action == AgentAction.SELECT_SLOT:
            return self._select_slot(state, plan)
        if plan.action == AgentAction.ASK_FOR_DETAILS:
            self._merge_details(state, plan)
            missing = self._missing_details(state)
            return Observation(
                type=ObservationType.MISSING_FIELDS,
                data={"fields": missing},
                requires_next_step=not missing,
            )
        if plan.action == AgentAction.PREPARE_BOOKING:
            return self._prepare_booking(state, plan)
        if plan.action == AgentAction.CANCEL_BOOKING:
            state.reset_scheduling()
            return Observation(type=ObservationType.CANCELLED)
        return Observation(type=ObservationType.SUCCESS)

    async def _get_availability(self, state: SessionState, plan: Plan) -> Observation:
        if plan.start_date is None or plan.end_date is None:
            return Observation(
                type=ObservationType.MISSING_FIELDS,
                data={"fields": ["date_range"]},
            )
        try:
            slots = await self._slots.available_slots(plan.start_date, plan.end_date)
        except ValueError as exc:
            return Observation(
                type=ObservationType.TOOL_ERROR,
                data={"error": str(exc)},
            )

        self._merge_details(state, plan)
        state.requested_start_date = plan.start_date
        state.requested_end_date = plan.end_date
        state.offered_slots = {f"S{index}": slot for index, slot in enumerate(slots, start=1)}
        state.selected_slot_id = None
        state.pending_booking = None

        return Observation(
            type=ObservationType.AVAILABLE_SLOTS,
            data={
                "slots": [
                    {
                        "id": slot_id,
                        "start": slot.start.isoformat(),
                        "end": slot.end.isoformat(),
                    }
                    for slot_id, slot in state.offered_slots.items()
                ],
                "empty": not state.offered_slots,
            },
        )

    def _select_slot(self, state: SessionState, plan: Plan) -> Observation:
        if not plan.slot_id or plan.slot_id not in state.offered_slots:
            return Observation(
                type=ObservationType.INVALID_SLOT,
                data={"slot_id": plan.slot_id},
            )

        state.selected_slot_id = plan.slot_id
        self._merge_details(state, plan)
        missing = self._missing_details(state)
        if missing:
            return Observation(
                type=ObservationType.MISSING_FIELDS,
                data={
                    "fields": missing,
                    "selected_slot_id": plan.slot_id,
                },
            )

        return Observation(
            type=ObservationType.SUCCESS,
            data={"selected_slot_id": plan.slot_id, "details_complete": True},
            requires_next_step=True,
        )

    def _prepare_booking(self, state: SessionState, plan: Plan) -> Observation:
        self._merge_details(state, plan)
        missing = self._missing_details(state)
        if missing:
            return Observation(
                type=ObservationType.MISSING_FIELDS,
                data={"fields": missing},
            )
        if not state.selected_slot_id or state.selected_slot_id not in state.offered_slots:
            return Observation(
                type=ObservationType.INVALID_SLOT,
                data={"slot_id": state.selected_slot_id},
            )

        slot = state.offered_slots[state.selected_slot_id]
        pending = PendingBooking(
            booking_id=uuid.uuid4().hex,
            slot=slot,
            visitor_name=state.visitor_name or "",
            visitor_email=state.visitor_email or "",
            subject=state.subject or "",
        )
        state.pending_booking = pending
        return Observation(
            type=ObservationType.AWAITING_CONFIRMATION,
            data={
                "booking_id": pending.booking_id,
                "slot_id": state.selected_slot_id,
                "start": pending.slot.start.isoformat(),
                "end": pending.slot.end.isoformat(),
                "visitor_name": pending.visitor_name,
                "visitor_email": pending.visitor_email,
                "subject": pending.subject,
            },
        )

    @staticmethod
    def _merge_details(state: SessionState, plan: Plan) -> None:
        if plan.visitor_name:
            state.visitor_name = plan.visitor_name.strip()
        if plan.visitor_email:
            state.visitor_email = plan.visitor_email.strip()
        if plan.subject:
            state.subject = plan.subject.strip()

    @staticmethod
    def _missing_details(state: SessionState) -> list[str]:
        missing: list[str] = []
        if not state.visitor_name:
            missing.append("visitor_name")
        if not state.visitor_email:
            missing.append("visitor_email")
        if not state.subject:
            missing.append("subject")
        return missing
