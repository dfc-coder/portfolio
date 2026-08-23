from __future__ import annotations

from typing import AsyncContextManager, Protocol

from app.domain.conversation import SessionState


class SessionStorePort(Protocol):
    def session(self, session_id: str) -> AsyncContextManager[SessionState]: ...

    async def get(self, session_id: str) -> SessionState: ...

    async def append_turn(
        self,
        state: SessionState,
        role: str,
        content: str,
    ) -> None: ...
