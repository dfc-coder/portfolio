from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from app.domain.conversation import ChatTurn, SessionState


class MemorySessionStore:
    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 8) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._sessions: dict[str, SessionState] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._active_counts: dict[str, int] = {}
        self._index_lock = asyncio.Lock()

    @asynccontextmanager
    async def session(self, session_id: str) -> AsyncIterator[SessionState]:
        async with self._index_lock:
            now = datetime.now(timezone.utc)
            self._purge_expired(now)
            state = self._get_or_create(session_id, now)
            session_lock = self._session_locks.setdefault(session_id, asyncio.Lock())
            self._active_counts[session_id] = self._active_counts.get(session_id, 0) + 1

        try:
            async with session_lock:
                state.last_activity = datetime.now(timezone.utc)
                yield state
                state.last_activity = datetime.now(timezone.utc)
        finally:
            async with self._index_lock:
                remaining = self._active_counts.get(session_id, 1) - 1
                if remaining > 0:
                    self._active_counts[session_id] = remaining
                else:
                    self._active_counts.pop(session_id, None)

    async def get(self, session_id: str) -> SessionState:
        async with self._index_lock:
            now = datetime.now(timezone.utc)
            self._purge_expired(now)
            return self._get_or_create(session_id, now)

    async def append_turn(self, state: SessionState, role: str, content: str) -> None:
        async with self._index_lock:
            state.turns.append(ChatTurn(role=role, content=content))
            if len(state.turns) > self._max_turns:
                state.turns[:] = state.turns[-self._max_turns :]
            state.last_activity = datetime.now(timezone.utc)

    def _get_or_create(self, session_id: str, now: datetime) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            state = SessionState(session_id=session_id)
            self._sessions[session_id] = state
        state.last_activity = now
        return state

    def _purge_expired(self, now: datetime) -> None:
        expired = [
            key
            for key, state in self._sessions.items()
            if self._active_counts.get(key, 0) == 0 and now - state.last_activity > self._ttl
        ]
        for key in expired:
            self._sessions.pop(key, None)
            self._session_locks.pop(key, None)
