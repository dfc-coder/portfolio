from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.ports.sessions import SessionStorePort

from .responder import Responder

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import PocketTraceRecorder, TurnTrace


class BusinessRepresentative:
    """Thin knowledge-agent orchestrator for the portfolio."""

    def __init__(
        self,
        sessions: SessionStorePort,
        responder: Responder,
        trace_recorder: PocketTraceRecorder | None = None,
    ) -> None:
        self._sessions = sessions
        self._responder = responder
        self._trace_recorder = trace_recorder
        self._trace_tasks: set[asyncio.Task[None]] = set()

    async def warm(self) -> None:
        await self._responder.warm()

    async def respond(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        trace: TurnTrace | None = (
            self._trace_recorder.start_turn(session_id, user_message)
            if self._trace_recorder is not None
            else None
        )
        response_chunks: list[str] = []

        try:
            async with self._sessions.session(session_id) as state:
                await self._sessions.append_turn(state, "user", user_message)

                async for chunk in self._responder.stream(state, trace):
                    response_chunks.append(chunk)
                    yield chunk

                await self._sessions.append_turn(
                    state,
                    "assistant",
                    "".join(response_chunks),
                )
        except Exception as exc:
            if trace is not None:
                trace.fail(exc)
            raise
        finally:
            if trace is not None and self._trace_recorder is not None:
                if trace.status == "running":
                    trace.finish(output={"response": "".join(response_chunks)})
                task = asyncio.create_task(self._trace_recorder.flush(trace))
                self._trace_tasks.add(task)
                task.add_done_callback(self._trace_tasks.discard)
