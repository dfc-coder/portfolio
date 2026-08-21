from __future__ import annotations

import re

from app.domain.conversation import SessionState
from app.domain.planning import AgentAction, Plan, VerificationResult

from .fsm import ConversationFSM
from .streaming_guard import find_stream_violation

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AgentVerifier:
    def __init__(self, fsm: ConversationFSM) -> None:
        self._fsm = fsm

    def verify_plan(self, state: SessionState, plan: Plan) -> VerificationResult:
        issues: list[str] = []
        if plan.action not in self._fsm.allowed_actions(state.stage):
            issues.append(
                f"Action {plan.action.value} is not allowed while stage={state.stage.value}."
            )

        if plan.action == AgentAction.GET_AVAILABILITY:
            if plan.start_date is None:
                issues.append("start_date is required for get_availability.")
            if plan.end_date is None:
                issues.append("end_date is required for get_availability.")
            if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
                issues.append("end_date must be on or after start_date.")

        if plan.action == AgentAction.SELECT_SLOT:
            if not plan.slot_id:
                issues.append("slot_id is required for select_slot.")
            elif plan.slot_id not in state.offered_slots:
                issues.append(f"slot_id {plan.slot_id} was not offered in this session.")

        if plan.visitor_email and not _EMAIL_RE.fullmatch(plan.visitor_email.strip()):
            issues.append("visitor_email is not valid.")

        if plan.action == AgentAction.PREPARE_BOOKING:
            if state.selected_slot_id is None:
                issues.append("A previously offered slot must be selected before prepare_booking.")
            elif state.selected_slot_id not in state.offered_slots:
                issues.append("The selected slot is stale or no longer present in offered_slots.")

            name = (plan.visitor_name or state.visitor_name or "").strip()
            email = (plan.visitor_email or state.visitor_email or "").strip()
            subject = (plan.subject or state.subject or "").strip()
            if len(name) < 2:
                issues.append("visitor_name is required before prepare_booking.")
            if not _EMAIL_RE.fullmatch(email):
                issues.append("A valid visitor_email is required before prepare_booking.")
            if len(subject) < 3:
                issues.append("subject is required before prepare_booking.")

        return VerificationResult(ok=not issues, issues=issues)

    def verify_business_response(
        self,
        state: SessionState,
        response: str,
    ) -> VerificationResult:
        del state
        issues: list[str] = []
        if not response.strip():
            issues.append("The response is empty.")

        violation = find_stream_violation(response)
        if violation == "owner_impersonation":
            issues.append("The representative must not impersonate the portfolio owner.")
        elif violation == "unverified_calendar_status":
            issues.append("The response must not claim calendar side effects from informational generation.")

        if len(response.split()) > 180:
            issues.append("The response is too long for the default concise business mode.")
        return VerificationResult(ok=not issues, issues=issues)
