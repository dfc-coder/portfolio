from __future__ import annotations

from collections.abc import AsyncIterator

from app.domain.routing import RouteDomain
from app.ports.sessions import SessionStorePort

from .responder import Responder
from .router import SemanticRouter
from .scheduler import Scheduler


class BusinessRepresentative:
    """Thin orchestrator: route, delegate, persist the resulting conversation turn."""

    def __init__(
        self,
        sessions: SessionStorePort,
        router: SemanticRouter,
        scheduler: Scheduler,
        responder: Responder,
    ) -> None:
        self._sessions = sessions
        self._router = router
        self._scheduler = scheduler
        self._responder = responder

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        async with self._sessions.session(session_id) as state:
            await self._sessions.append_turn(state, "user", user_message)

            decision = await self._router.route(state, user_message)
            state.current_focus = decision.domain

            if decision.domain == RouteDomain.SCHEDULING:
                reply = await self._scheduler.handle(state, user_message, decision.relation)
                if not reply.not_applicable:
                    await self._sessions.append_turn(state, "assistant", reply.text)
                    yield reply.text
                    return

                fallback = await self._router.route_non_scheduling(state, user_message)
                state.current_focus = fallback.domain

            chunks: list[str] = []
            async for chunk in self._responder.stream(state):
                chunks.append(chunk)
                yield chunk
            await self._sessions.append_turn(state, "assistant", "".join(chunks))
