from __future__ import annotations

import re


_RESTRICTED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # English negative forms ("I am not Diego" / "I'm not Diego") do not match
    # because `not` sits between the verb and the owner name. In Spanish we need
    # an explicit negative lookbehind so the safe disclaimer "No soy Diego" is
    # not mistaken for impersonation.
    (
        re.compile(
            r"(?:\b(?:i am|i'm)\s+diego\b|(?<!no )\b(?:yo\s+)?soy\s+diego\b)",
            re.IGNORECASE,
        ),
        "owner_impersonation",
    ),
    (
        re.compile(
            r"\b(?:the meeting|it|la reuni[oó]n|la cita)\s+(?:is|was|est[aá]|qued[oó]|fue)\s+"
            r"(?:already\s+|ya\s+)?(?:booked|scheduled|agendad[oa]|reservad[oa])\b",
            re.IGNORECASE,
        ),
        "unverified_calendar_status",
    ),
    (
        re.compile(
            r"\b(?:i|we|yo)\s+(?:booked|scheduled|agend[eé]|reserv[eé])\b",
            re.IGNORECASE,
        ),
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


class StreamGuard:
    """Tiny rolling holdback with context-aware scanning across flush boundaries."""

    def __init__(self, holdback_chars: int = 48, scan_context_chars: int = 32) -> None:
        self._holdback_chars = max(24, holdback_chars)
        self._scan_context_chars = max(8, scan_context_chars)
        self._scan_context = ""
        self._pending = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""

        self._pending += chunk
        self._raise_if_unsafe()

        flush_chars = len(self._pending) - self._holdback_chars
        if flush_chars <= 0:
            return ""

        ready = self._pending[:flush_chars]
        self._pending = self._pending[flush_chars:]
        self._scan_context = (self._scan_context + ready)[-self._scan_context_chars :]
        return ready

    def finish(self) -> str:
        self._raise_if_unsafe()
        ready = self._pending
        self._pending = ""
        self._scan_context = ""
        return ready

    def _raise_if_unsafe(self) -> None:
        violation = find_stream_violation(self._scan_context + self._pending)
        if violation:
            raise UnsafeStreamOutput(violation)
