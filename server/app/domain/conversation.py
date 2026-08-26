from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .routing import RouteDomain


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


@dataclass
class SessionState:
    session_id: str
    current_focus: RouteDomain = RouteDomain.BUSINESS
    turns: list[ChatTurn] = field(default_factory=list)
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
