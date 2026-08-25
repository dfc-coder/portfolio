from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.profile import SchedulingProfile

_REJECTION_PATTERNS = (
    r"^\s*(?:cancel|cancel it|cancel the meeting|don't book(?: it)?|do not book(?: it)?|another time)\s*[.!]?\s*$",
    r"^\s*(?:cancelá|cancela|cancelar|no agendes(?: nada)?|no lo agendes|otro horario|otra hora)\s*[.!]?\s*$",
)


@dataclass(frozen=True)
class SchedulingPolicy:
    config: SchedulingProfile

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.config.timezone)

    def is_rejection(self, text: str) -> bool:
        normalized = text.strip().lower()
        return any(
            re.search(pattern, normalized, re.IGNORECASE)
            for pattern in _REJECTION_PATTERNS
        )

    def validate_date_window(
        self,
        start: datetime,
        end: datetime,
        now: datetime,
    ) -> None:
        local_now = now.astimezone(self.timezone)
        if end <= start:
            raise ValueError("The availability window must end after it starts.")
        if start < local_now + timedelta(hours=self.config.min_notice_hours):
            raise ValueError("The requested time is inside the minimum notice window.")
        if start > local_now + timedelta(days=self.config.max_days_ahead):
            raise ValueError("The requested time is too far in the future.")
