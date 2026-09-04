from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Session:
    session_id: str
    turns: list[Message] = field(default_factory=list)
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MemorySessions:
    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 8) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._sessions: dict[str, Session] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._index_lock = asyncio.Lock()

    @asynccontextmanager
    async def open(self, session_id: str) -> AsyncIterator[Session]:
        async with self._index_lock:
            now = datetime.now(timezone.utc)
            self._purge(now)
            session = self._sessions.setdefault(session_id, Session(session_id=session_id))
            lock = self._locks.setdefault(session_id, asyncio.Lock())

        async with lock:
            session.last_activity = datetime.now(timezone.utc)
            yield session
            if len(session.turns) > self._max_turns:
                session.turns[:] = session.turns[-self._max_turns :]
            session.last_activity = datetime.now(timezone.utc)

    def _purge(self, now: datetime) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_activity > self._ttl
            and not self._locks.get(session_id, asyncio.Lock()).locked()
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
            self._locks.pop(session_id, None)
