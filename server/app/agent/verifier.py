from __future__ import annotations

import re

from app.domain.conversation import SessionState
from app.domain.planning import VerificationResult

_OWNER_IMPERSONATION_RE = re.compile(r"\b(?:i am|i'm|soy)\s+diego\b", re.IGNORECASE)
_FALSE_BOOKING_RE = re.compile(r"\b(?:booked|scheduled|on the calendar|agendad[oa]|reservad[oa])\b", re.IGNORECASE)


class AgentVerifier:
    """Post-stream observability checks; write safety lives in CapabilitySafetyGate."""

    def verify_business_response(self, state: SessionState, response: str) -> VerificationResult:
        issues: list[str] = []
        if not response.strip():
            issues.append("The response is empty.")
        if _OWNER_IMPERSONATION_RE.search(response):
            issues.append("The representative must not impersonate the portfolio owner.")
        if state.scheduling.pending_booking is None and _FALSE_BOOKING_RE.search(response):
            issues.append("The response must not claim a meeting is booked without calendar success.")
        if len(response.split()) > 180:
            issues.append("The response is too long for the default concise business mode.")
        return VerificationResult(ok=not issues, issues=issues)
