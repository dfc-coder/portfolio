from __future__ import annotations

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.semantics import DialogueAct, SchedulingCommand


class BeliefUpdater:
    def apply(self, state: SessionState, command: SchedulingCommand) -> frozenset[str]:
        if command.act == DialogueAct.NOT_APPLICABLE:
            return self.facts(state, command)

        state.active_workflow = ActiveWorkflow.SCHEDULING
        memory = state.scheduling

        if command.start_date is not None:
            memory.requested_start_date = command.start_date
            memory.requested_end_date = command.end_date or command.start_date
            # A new date request invalidates derived availability/selection.
            memory.offered_slots.clear()
            memory.selected_slot_id = None
            memory.pending_booking = None

        if command.visitor_name:
            memory.visitor_name = command.visitor_name.strip()
        if command.visitor_email:
            memory.visitor_email = command.visitor_email.strip()
        if command.subject:
            memory.subject = command.subject.strip()

        return self.facts(state, command)

    @staticmethod
    def facts(state: SessionState, command: SchedulingCommand) -> frozenset[str]:
        facts = set(state.scheduling.facts())
        if state.active_workflow == ActiveWorkflow.SCHEDULING:
            facts.add("active_workflow")
        if command.start_date is not None:
            facts.add("date_input")
        if command.slot_id:
            facts.add("slot_reference")
        if command.act == DialogueAct.CONFIRM:
            facts.add("semantic_confirmation")
        return frozenset(facts)
