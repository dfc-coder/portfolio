from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.conversation import ActiveWorkflow
from app.domain.routing import RouteDomain, RouteRelation
from app.ports.sessions import SessionStorePort
from app.scheduling.admission import is_new_scheduling_request
from app.scheduling.presenter import SchedulingPresenter

from .responder import Responder
from .scheduler import Scheduler

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import PocketTraceRecorder, TurnTrace


class BusinessRepresentative:
    """Thin orchestrator: operational admission, knowledge retrieval, response."""

    def __init__(
        self,
        sessions: SessionStorePort,
        scheduler: Scheduler,
        scheduling_presenter: SchedulingPresenter,
        responder: Responder,
        trace_recorder: PocketTraceRecorder | None = None,
    ) -> None:
        self._sessions = sessions
        self._scheduler = scheduler
        self._scheduling_presenter = scheduling_presenter
        self._responder = responder
        self._trace_recorder = trace_recorder
        self._trace_tasks: set[asyncio.Task[None]] = set()

    async def warm(self) -> None:
        await self._responder.warm()

    async def respond(
        self,
        session_id: str,
        user_message: str,
        locale: str = "en",
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

                active_scheduling = (
                    state.active_workflow == ActiveWorkflow.SCHEDULING
                )
                should_try_scheduler = active_scheduling or is_new_scheduling_request(
                    user_message
                )

                if should_try_scheduler:
                    relation = (
                        RouteRelation.CONTINUE
                        if active_scheduling
                        else RouteRelation.NEW
                    )
                    scheduler_started = time.perf_counter()
                    reply = await self._scheduler.handle(
                        state,
                        user_message,
                        relation,
                    )
                    if trace is not None:
                        trace.add_span(
                            "scheduler",
                            (time.perf_counter() - scheduler_started) * 1000,
                            input={
                                "message": user_message,
                                "relation": relation.value,
                                "admitted": True,
                            },
                            output=reply.model_dump(mode="json"),
                        )

                    if not reply.not_applicable:
                        state.current_focus = RouteDomain.SCHEDULING
                        text = self._scheduling_presenter.render(reply, locale)
                        if trace is not None:
                            trace.add_attributes(
                                route=RouteDomain.SCHEDULING.value,
                                route_relation=relation.value,
                                route_source="scheduling:admission",
                            )
                        await self._sessions.append_turn(state, "assistant", text)
                        response_chunks.append(text)
                        yield text
                        return

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
