from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.domain.conversation import ChatTurn, SessionState


class MemorySessionStore:
    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 8) -> None:
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
