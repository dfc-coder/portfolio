from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import Route, RouteRelation
from app.ports.sessions import SessionStorePort
from app.portfolio.search import PortfolioSearch

from .responder import Responder
from .router import SemanticRouter
from .scheduler import Scheduler

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import PocketTraceRecorder, TurnTrace


_ABSTAIN_REPLY = (
    "No pude determinar con suficiente certeza si querés consultar información o iniciar "
    "una acción. ¿Podés reformularlo?"
)


class BusinessRepresentative:
    """Thin orchestrator: route, invoke one business capability, persist the turn."""

    def __init__(
        self,
        sessions: SessionStorePort,
        router: SemanticRouter,
        portfolio: PortfolioSearch,
        scheduler: Scheduler,
        responder: Responder,
        trace_recorder: PocketTraceRecorder | None = None,
    ) -> None:
        self._sessions = sessions
        self._router = router
        self._portfolio = portfolio
        self._scheduler = scheduler
        self._responder = responder
        self._trace_recorder = trace_recorder
        self._trace_tasks: set[asyncio.Task[None]] = set()

    async def warm(self) -> None:
        await asyncio.gather(
            self._router.warm(),
            self._portfolio.warm(),
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
                        route=decision.domain.value if decision.domain else "abstain",
                        route_source=decision.source,
                        intent=decision.intent.value if decision.intent else "unknown",
                        route_accepted=decision.accepted,
                        route_confidence=decision.confidence,
                        route_margin=decision.margin,
                    )

                if not decision.accepted:
                    await self._sessions.append_turn(state, "assistant", _ABSTAIN_REPLY)
                    response_chunks.append(_ABSTAIN_REPLY)
                    yield _ABSTAIN_REPLY
                    return

                if decision.domain is None:
                    raise RuntimeError("accepted routing decision has no business route")
                state.current_focus = decision.domain

                if decision.domain == Route.SCHEDULING:
                    relation = self._scheduling_relation(state)
                    scheduler_started = time.perf_counter()
                    reply = await self._scheduler.handle(state, user_message, relation)
                    if trace is not None:
                        trace.add_span(
                            "scheduler",
                            (time.perf_counter() - scheduler_started) * 1000,
                            input={
                                "message": user_message,
                                "relation": relation.value,
                            },
                            output=reply.model_dump(mode="json"),
                        )
                    await self._sessions.append_turn(state, "assistant", reply.text)
                    response_chunks.append(reply.text)
                    yield reply.text
                    return

                if decision.domain == Route.PORTFOLIO:
                    query = self._portfolio_query(state)
                    search_started = time.perf_counter()
                    result = await self._portfolio.search(query)
                    if trace is not None:
                        trace.add_span(
                            "portfolio_search",
                            (time.perf_counter() - search_started) * 1000,
                            input={"query": query},
                            output={
                                "facts": [
                                    {"source": fact.source, "text": fact.text}
                                    for fact in result.facts
                                ]
                            },
                        )
                    async for chunk in self._responder.stream(
                        state,
                        trace,
                        evidence=result.facts,
                    ):
                        response_chunks.append(chunk)
                        yield chunk
                else:
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

    @staticmethod
    def _scheduling_relation(state: SessionState) -> RouteRelation:
        if state.active_workflow == ActiveWorkflow.SCHEDULING:
            return RouteRelation.CONTINUE
        return RouteRelation.NEW

    @staticmethod
    def _portfolio_query(state: SessionState) -> str:
        recent_user_turns = [
            turn.content
            for turn in state.turns
            if turn.role == "user"
        ][-2:]
        return "\n".join(recent_user_turns)
