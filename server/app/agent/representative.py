from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.routing import RouteDomain
from app.ports.sessions import SessionStorePort

from .responder import Responder
from .router import SemanticRouter
from .scheduler import Scheduler

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import PocketTraceRecorder, TurnTrace


class BusinessRepresentative:
    """Thin orchestrator: route, delegate, persist the resulting conversation turn."""

    def __init__(
        self,
        sessions: SessionStorePort,
        router: SemanticRouter,
        scheduler: Scheduler,
        responder: Responder,
        trace_recorder: PocketTraceRecorder | None = None,
    ) -> None:
        self._sessions = sessions
        self._router = router
        self._scheduler = scheduler
        self._responder = responder
        self._trace_recorder = trace_recorder
        self._trace_tasks: set[asyncio.Task[None]] = set()

    async def warm(self) -> None:
        await asyncio.gather(
            self._router.warm(),
            self._responder.warm(),
        )

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        trace: TurnTrace | None = (
            self._trace_recorder.start_turn(session_id, user_message)
            if self._trace_recorder is not None
            else None
        )
        response_chunks: list[str] = []

        try:
            async with self._sessions.session(session_id) as state:
                await self._sessions.append_turn(state, "user", user_message)

                route_started = time.perf_counter()
                decision = await self._router.route(state, user_message)
                if trace is not None:
                    trace.add_span(
                        "router",
                        (time.perf_counter() - route_started) * 1000,
                        input={"message": user_message},
                        output=decision.model_dump(mode="json"),
                    )
                    trace.add_attributes(
                        route=decision.domain.value,
                        route_relation=decision.relation.value,
                        route_source=decision.source,
                    )
                state.current_focus = decision.domain

                if decision.domain == RouteDomain.SCHEDULING:
                    scheduler_started = time.perf_counter()
                    reply = await self._scheduler.handle(state, user_message, decision.relation)
                    if trace is not None:
                        trace.add_span(
                            "scheduler",
                            (time.perf_counter() - scheduler_started) * 1000,
                            input={
                                "message": user_message,
                                "relation": decision.relation.value,
                            },
                            output=reply.model_dump(mode="json"),
                        )
                    if not reply.not_applicable:
                        await self._sessions.append_turn(state, "assistant", reply.text)
                        response_chunks.append(reply.text)
                        yield reply.text
                        return

                    fallback_started = time.perf_counter()
                    fallback = await self._router.route_non_scheduling(state, user_message)
                    if trace is not None:
                        trace.add_span(
                            "router_non_scheduling",
                            (time.perf_counter() - fallback_started) * 1000,
                            input={"message": user_message},
                            output=fallback.model_dump(mode="json"),
                        )
                        trace.add_attributes(
                            route=fallback.domain.value,
                            route_relation=fallback.relation.value,
                            route_source=fallback.source,
                        )
                    state.current_focus = fallback.domain

                async for chunk in self._responder.stream(state, trace):
                    response_chunks.append(chunk)
                    yield chunk
                await self._sessions.append_turn(state, "assistant", "".join(response_chunks))
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
