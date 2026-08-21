from __future__ import annotations

import re


_RESTRICTED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:i am|i'm|soy)\s+diego\b", re.IGNORECASE), "owner_impersonation"),
    (re.compile(r"\b(?:the meeting|it|la reuni[oó]n|la cita)\s+(?:is|was|est[aá]|qued[oó]|fue)\s+(?:already\s+|ya\s+)?(?:booked|scheduled|agendad[oa]|reservad[oa])\b", re.IGNORECASE), "unverified_calendar_status"),
    (re.compile(r"\b(?:i|we|yo)\s+(?:booked|scheduled|agend[eé]|reserv[eé])\b", re.IGNORECASE), "unverified_calendar_status"),
    (re.compile(r"\b(?:calendar event (?:was )?created|created (?:a )?calendar event)\b", re.IGNORECASE), "unverified_calendar_status"),
    (re.compile(r"\b(?:invitation (?:was )?sent|invitaci[oó]n (?:fue )?enviada)\b", re.IGNORECASE), "unverified_calendar_status"),
)


class UnsafeStreamOutput(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def find_stream_violation(text: str) -> str | None:
    for pattern, reason in _RESTRICTED_PATTERNS:
        if pattern.search(text):
            return reason
    return None


class StreamGuard:
    """Tiny rolling holdback: real streaming with a narrow operational-claim boundary."""

    def __init__(self, holdback_chars: int = 48) -> None:
        self._holdback_chars = max(24, holdback_chars)
        self._pending = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._pending += chunk
        violation = find_stream_violation(self._pending)
        if violation:
            raise UnsafeStreamOutput(violation)
        flush_chars = len(self._pending) - self._holdback_chars
        if flush_chars <= 0:
            return ""
        ready = self._pending[:flush_chars]
        self._pending = self._pending[flush_chars:]
        return ready

    def finish(self) -> str:
        violation = find_stream_violation(self._pending)
        if violation:
            raise UnsafeStreamOutput(violation)
        ready = self._pending
        self._pending = ""
        return ready
