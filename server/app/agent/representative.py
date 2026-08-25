from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.conversation import ActiveWorkflow
from app.domain.routing import RouteDomain, RouteRelation
from app.ports.sessions import SessionStorePort
from app.scheduling.admission import (
    availability_clarification,
    is_availability_request,
    is_new_scheduling_request,
)

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
        responder: Responder,
        trace_recorder: PocketTraceRecorder | None = None,
    ) -> None:
        self._sessions = sessions
        self._scheduler = scheduler
        self._responder = responder
        self._trace_recorder = trace_recorder
        self._trace_tasks: set[asyncio.Task[None]] = set()

    async def warm(self) -> None:
        await self._responder.warm()

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

                active_scheduling = (
                    state.active_workflow == ActiveWorkflow.SCHEDULING
                )
                new_availability_request = (
                    not active_scheduling and is_availability_request(user_message)
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
                        if trace is not None:
                            trace.add_attributes(
                                route=RouteDomain.SCHEDULING.value,
                                route_relation=relation.value,
                                route_source="scheduling:admission",
                            )
                        await self._sessions.append_turn(
                            state,
                            "assistant",
                            reply.text,
                        )
                        response_chunks.append(reply.text)
                        yield reply.text
                        return

                    # A bare availability question has no date to parse yet. Keep it
                    # on the operational path and ask only for the missing date/range;
                    # do not fall through to RAG where the model can invent tool limits.
                    if new_availability_request:
                        state.active_workflow = ActiveWorkflow.SCHEDULING
                        state.current_focus = RouteDomain.SCHEDULING
                        text = availability_clarification(user_message)
                        if trace is not None:
                            trace.add_attributes(
                                route=RouteDomain.SCHEDULING.value,
                                route_relation=RouteRelation.NEW.value,
                                route_source="scheduling:availability",
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
