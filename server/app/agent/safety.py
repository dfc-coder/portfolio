from __future__ import annotations

import re

from app.domain.capabilities import CapabilitySpec, SideEffect
from app.domain.conversation import SessionState
from app.domain.planning import VerificationResult
from app.domain.semantics import SchedulingCommand
from app.scheduling.policy import SchedulingPolicy

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class CapabilitySafetyGate:
    """Deterministic invariants only; semantic routing never lives here."""

    def __init__(self, policy: SchedulingPolicy) -> None:
        self._policy = policy

    def is_explicit_confirmation(self, user_message: str) -> bool:
        return self._policy.is_explicit_confirmation(user_message)

    def validate(self, capability: CapabilitySpec, state: SessionState, command: SchedulingCommand, user_message: str) -> VerificationResult:
        issues: list[str] = []
        memory = state.scheduling

        if capability.side_effect == SideEffect.WRITE and capability.requires_confirmation:
            if not self.is_explicit_confirmation(user_message):
                issues.append("A write capability requires explicit visitor confirmation.")

        if capability.name == "calendar.create_booking":
            pending = memory.pending_booking
            if pending is None:
                issues.append("No pending booking exists.")
            else:
                if not _EMAIL_RE.fullmatch(pending.visitor_email.strip()):
                    issues.append("Pending booking email is invalid.")
                if memory.selected_slot_id is None or memory.selected_slot_id not in memory.offered_slots:
                    issues.append("Pending booking must reference a previously offered selected slot.")

        if capability.name == "scheduling.select_slot":
            if not command.slot_id or command.slot_id not in memory.offered_slots:
                issues.append("The requested slot was not offered in this session.")

        return VerificationResult(ok=not issues, issues=issues)
