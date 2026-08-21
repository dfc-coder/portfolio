from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Final

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
from .verifier import AgentVerifier

_CHUNK_SIZE: Final[int] = 24


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
            async for chunk in self._chunk(text):
                yield chunk
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
        async for chunk in self._chunk(text):
            yield chunk

    async def _knowledge_answer(self, state: SessionState) -> AsyncIterator[str]:
        candidate = await self._renderer.business_answer(state)
        verification = self._verifier.verify_business_response(state, candidate)
        if not verification.ok and self._max_repairs > 0:
            candidate = await self._renderer.repair_business_answer(
                state,
                candidate,
                verification.issues,
            )
            verification = self._verifier.verify_business_response(state, candidate)
        if not verification.ok:
            candidate = (
                "No tengo información suficiente para responder eso con precisión."
                if self._looks_spanish(state.turns[-1].content)
                else "I don't have enough information to answer that accurately."
            )

        await self._sessions.append_turn(state, "assistant", candidate)
        async for chunk in self._chunk(candidate):
            yield chunk

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
        async for chunk in self._chunk(text):
            yield chunk

    @staticmethod
    async def _chunk(text: str, size: int = _CHUNK_SIZE) -> AsyncIterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]

    @staticmethod
    def _looks_spanish(text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered.split() for token in ("que", "qué", "hola", "quiero", "puedo")) or any(
            char in lowered for char in "áéíóúñ"
        )
