from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.domain.conversation import ActiveWorkflow, ConversationStage, SessionState
from app.domain.planning import Observation, ObservationType
from app.domain.routing import RouteDomain
from app.ports.calendar import CalendarPort
from app.ports.sessions import SessionStorePort
from app.scheduling.policy import SchedulingPolicy

from .executor import ActionExecutor
from .fsm import ConversationFSM
from .planner import PlanningFailure, StructuredPlanner
from .renderer import HybridRenderer
from .semantic_router import CascadingSemanticRouter
from .streaming_guard import StreamingOutputGuard, UnsafeStreamOutput
from .verifier import AgentVerifier

logger = logging.getLogger(__name__)


class BusinessRepresentative:
    def __init__(
        self,
        sessions: SessionStorePort,
        policy: SchedulingPolicy,
        calendar: CalendarPort,
        router: CascadingSemanticRouter,
        planner: StructuredPlanner,
        executor: ActionExecutor,
        fsm: ConversationFSM,
        verifier: AgentVerifier,
        renderer: HybridRenderer,
        *,
        max_steps: int = 3,
        max_repairs: int = 1,
    ) -> None:
        self._sessions = sessions
        self._policy = policy
        self._calendar = calendar
        self._router = router
        self._planner = planner
        self._executor = executor
        self._fsm = fsm
        self._verifier = verifier
        self._renderer = renderer
        self._max_steps = max(1, max_steps)
        self._max_repairs = max(0, max_repairs)

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        state = await self._sessions.get(session_id)
        await self._sessions.append_turn(state, "user", user_message)

        # Calendar writes/cancellation remain deterministic safety boundaries.
        if state.pending_booking is not None and (
            self._policy.is_explicit_confirmation(user_message)
            or self._policy.is_rejection(user_message)
        ):
            async for chunk in self._handle_pending_booking(state, user_message):
                yield chunk
            return

        if state.stage == ConversationStage.COMPLETE and state.active_workflow is None:
            state.stage = ConversationStage.BUSINESS

        decision = await self._router.route(state, user_message)
        state.current_focus = decision.domain

        if decision.domain != RouteDomain.SCHEDULING:
            async for chunk in self._knowledge_answer(state):
                yield chunk
            return

        if state.pending_booking is not None:
            text = self._renderer.confirmation_reminder(state, user_message)
            await self._sessions.append_turn(state, "assistant", text)
            yield text
            return

        if state.active_workflow is None:
            state.active_workflow = ActiveWorkflow.SCHEDULING
        state.current_focus = RouteDomain.SCHEDULING

        observation: Observation | None = None
        repairs = 0

        for _ in range(self._max_steps):
            try:
                plan = await self._planner.plan(state, user_message, observation)
            except PlanningFailure as exc:
                if repairs >= self._max_repairs:
                    observation = Observation(
                        type=ObservationType.TOOL_ERROR,
                        data={"error": str(exc)},
                    )
                    break
                repairs += 1
                try:
                    plan = await self._planner.repair(
                        state,
                        user_message,
                        [str(exc)],
                        observation,
                    )
                except PlanningFailure:
                    observation = Observation(type=ObservationType.TOOL_ERROR)
                    break

            verification = self._verifier.verify_plan(state, plan)
            if not verification.ok:
                if repairs >= self._max_repairs:
                    observation = Observation(
                        type=ObservationType.TOOL_ERROR,
                        data={"issues": verification.issues},
                    )
                    break
                repairs += 1
                try:
                    plan = await self._planner.repair(
                        state,
                        user_message,
                        verification.issues,
                        observation,
                    )
                except PlanningFailure:
                    observation = Observation(type=ObservationType.TOOL_ERROR)
                    break
                verification = self._verifier.verify_plan(state, plan)
                if not verification.ok:
                    observation = Observation(
                        type=ObservationType.TOOL_ERROR,
                        data={"issues": verification.issues},
                    )
                    break

            observation = await self._executor.execute(state, plan)
            self._fsm.transition(state, plan, observation)
            if not observation.requires_next_step:
                break

        if observation is None:
            observation = Observation(type=ObservationType.TOOL_ERROR)

        text = self._renderer.render_observation(
            observation,
            user_message,
            self._policy.config.timezone,
        )
        await self._sessions.append_turn(state, "assistant", text)
        yield text

    async def _knowledge_answer(self, state: SessionState) -> AsyncIterator[str]:
        guard = StreamingOutputGuard()
        emitted: list[str] = []

        try:
            async for chunk in self._renderer.stream_business_answer(state):
                ready = guard.feed(chunk)
                if ready:
                    emitted.append(ready)
                    yield ready

            tail = guard.finish()
            if tail:
                emitted.append(tail)
                yield tail
        except UnsafeStreamOutput as exc:
            logger.warning(
                "blocked unsafe streamed business output reason=%s stage=%s workflow=%s",
                exc.reason,
                state.stage.value,
                state.active_workflow.value if state.active_workflow else "none",
            )
            fallback = self._renderer.safety_fallback(state)
            if emitted:
                fallback = f" {fallback}"
            emitted.append(fallback)
            yield fallback

        text = "".join(emitted)
        if not text.strip():
            text = self._renderer.safety_fallback(state)
            emitted.append(text)
            yield text

        await self._sessions.append_turn(state, "assistant", text)

        # Lightweight post-stream monitoring only. It never delays or rewrites the stream.
        verification = self._verifier.verify_business_response(state, text)
        if not verification.ok:
            logger.warning(
                "post-stream business verification issues=%s stage=%s workflow=%s",
                verification.issues,
                state.stage.value,
                state.active_workflow.value if state.active_workflow else "none",
            )

    async def _handle_pending_booking(
        self,
        state: SessionState,
        user_message: str,
    ) -> AsyncIterator[str]:
        if self._policy.is_rejection(user_message):
            state.reset_scheduling()
            observation = Observation(type=ObservationType.CANCELLED)
            text = self._renderer.render_observation(
                observation,
                user_message,
                self._policy.config.timezone,
            )
        elif self._policy.is_explicit_confirmation(user_message):
            pending = state.pending_booking
            if pending is None:
                return
            try:
                result = await self._calendar.create_booking(
                    pending,
                    self._policy.config.timezone,
                )
            except Exception:
                observation = Observation(
                    type=ObservationType.TOOL_ERROR,
                    data={"error": "calendar_write_failed"},
                )
                text = self._renderer.render_observation(
                    observation,
                    user_message,
                    self._policy.config.timezone,
                )
            else:
                state.last_booking_id = result.booking_id
                state.pending_booking = None
                state.active_workflow = None
                state.current_focus = RouteDomain.SCHEDULING
                state.stage = ConversationStage.COMPLETE
                observation = Observation(
                    type=ObservationType.BOOKED,
                    data={
                        "start": pending.slot.start.isoformat(),
                        "end": pending.slot.end.isoformat(),
                        "subject": pending.subject,
                        "visitor_email": pending.visitor_email,
                    },
                )
                text = self._renderer.render_observation(
                    observation,
                    user_message,
                    self._policy.config.timezone,
                )
        else:
            text = self._renderer.confirmation_reminder(state, user_message)

        await self._sessions.append_turn(state, "assistant", text)
        yield text
