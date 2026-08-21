from __future__ import annotations

import re


_RESTRICTED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:i am|i'm|soy)\s+diego\b", re.IGNORECASE),
        "owner_impersonation",
    ),
    (
        re.compile(
            r"\b(?:booked|scheduled|agendad[oa]|reservad[oa])\b",
            re.IGNORECASE,
        ),
        "unverified_calendar_status",
    ),
    (
        re.compile(r"\bon the calendar\b", re.IGNORECASE),
        "unverified_calendar_status",
    ),
    (
        re.compile(
            r"\b(?:calendar event (?:was )?created|created (?:a )?calendar event)\b",
            re.IGNORECASE,
        ),
        "unverified_calendar_status",
    ),
    (
        re.compile(
            r"\b(?:invitation (?:was )?sent|invitaci[oó]n (?:fue )?enviada)\b",
            re.IGNORECASE,
        ),
        "unverified_calendar_status",
    ),
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


class StreamingOutputGuard:
    """Small rolling holdback that blocks restricted claims before they reach SSE."""

    def __init__(self, holdback_chars: int = 32) -> None:
        self._holdback_chars = max(16, holdback_chars)
        self._pending = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""

        self._pending += chunk
        violation = find_stream_violation(self._pending)
        if violation is not None:
            raise UnsafeStreamOutput(violation)

        flush_chars = len(self._pending) - self._holdback_chars
        if flush_chars <= 0:
            return ""

        ready = self._pending[:flush_chars]
        self._pending = self._pending[flush_chars:]
        return ready

    def finish(self) -> str:
        violation = find_stream_violation(self._pending)
        if violation is not None:
            raise UnsafeStreamOutput(violation)

        ready = self._pending
        self._pending = ""
        return ready
