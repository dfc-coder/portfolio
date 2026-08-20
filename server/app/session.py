from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


@dataclass(frozen=True)
class OfferedSlot:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PendingBooking:
    booking_id: str
    slot: OfferedSlot
    visitor_name: str
    visitor_email: str
    subject: str


@dataclass
class SessionState:
    session_id: str
    turns: list[ChatTurn] = field(default_factory=list)
    offered_slots: list[OfferedSlot] = field(default_factory=list)
    pending_booking: PendingBooking | None = None
    last_booking_id: str | None = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionStore:
    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 12) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> SessionState:
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired = [
                key
                for key, state in self._sessions.items()
                if now - state.last_activity > self._ttl
            ]
            for key in expired:
                del self._sessions[key]

            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id)
                self._sessions[session_id] = state
            state.last_activity = now
            return state

    async def append_turn(self, state: SessionState, role: str, content: str) -> None:
        async with self._lock:
            state.turns.append(ChatTurn(role=role, content=content))
            if len(state.turns) > self._max_turns:
                state.turns[:] = state.turns[-self._max_turns :]
            state.last_activity = datetime.now(timezone.utc)
