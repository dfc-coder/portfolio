from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.profile import SchedulingProfile

_EXPLICIT_CONFIRMATIONS = {
    "yes",
    "yes please",
    "yes, please",
    "yes, book it",
    "yes book it",
    "yes, schedule it",
    "yes schedule it",
    "confirm",
    "confirmed",
    "book it",
    "schedule it",
    "go ahead",
    "si",
    "sí",
    "si por favor",
    "sí por favor",
    "si, por favor",
    "sí, por favor",
    "si, confirmo",
    "sí, confirmo",
    "confirmo",
    "confirmado",
    "agendalo",
    "agéndalo",
    "reservalo",
    "resérvalo",
    "dale",
    "dale, agendalo",
    "dale, agéndalo",
}

_REJECTION_PATTERNS = (
    r"\b(?:no|cancel|cancel it|don't book|do not book|another time)\b",
    r"\b(?:no|cancelá|cancela|no agendes|otro horario|otra hora)\b",
)


@dataclass(frozen=True)
class SchedulingPolicy:
    config: SchedulingProfile

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.config.timezone)

    def is_explicit_confirmation(self, text: str) -> bool:
        normalized = re.sub(r"[.!]+$", "", text.strip().lower())
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized in _EXPLICIT_CONFIRMATIONS

    def is_rejection(self, text: str) -> bool:
        normalized = text.strip().lower()
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _REJECTION_PATTERNS)

    def validate_date_window(self, start: datetime, end: datetime, now: datetime) -> None:
        local_now = now.astimezone(self.timezone)
        if end <= start:
            raise ValueError("The availability window must end after it starts.")
        if start < local_now + timedelta(hours=self.config.min_notice_hours):
            raise ValueError("The requested time is inside the minimum notice window.")
        if start > local_now + timedelta(days=self.config.max_days_ahead):
            raise ValueError("The requested time is too far in the future.")
