from __future__ import annotations

from typing import Protocol

from app.domain.conversation import SessionState


class SessionStorePort(Protocol):
    async def get(self, session_id: str) -> SessionState: ...

    async def append_turn(
        self,
        state: SessionState,
        role: str,
        content: str,
    ) -> None: ...
