from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.domain.conversation import SessionState
from app.domain.planning import ObservationType
from app.domain.routing import RouteDomain
from app.domain.semantics import DialogueAct
from app.ports.sessions import SessionStorePort
from app.scheduling.policy import SchedulingPolicy

from .belief import BeliefUpdater
from .interpreter import SchedulingInterpreter
from .loop import BoundedCapabilityLoop
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
        router: CascadingSemanticRouter,
        interpreter: SchedulingInterpreter,
        belief: BeliefUpdater,
        loop: BoundedCapabilityLoop,
        verifier: AgentVerifier,
        renderer: HybridRenderer,
    ) -> None:
        self._sessions = sessions
        self._policy = policy
        self._router = router
        self._interpreter = interpreter
        self._belief = belief
        self._loop = loop
        self._verifier = verifier
        self._renderer = renderer

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        state = await self._sessions.get(session_id)
        await self._sessions.append_turn(state, "user", user_message)

        decision = await self._router.route(state, user_message)
        state.current_focus = decision.domain

        if decision.domain != RouteDomain.SCHEDULING:
            async for chunk in self._knowledge_answer(state):
                yield chunk
            return

        command = await self._interpreter.interpret(state, user_message, decision.relation)
        if command.act == DialogueAct.NOT_APPLICABLE:
            fallback = await self._router.route_non_scheduling(state, user_message)
            state.current_focus = fallback.domain
            async for chunk in self._knowledge_answer(state):
                yield chunk
            return

        self._belief.apply(state, command)
        observation = await self._loop.run(state, command, user_message)

        if observation.type == ObservationType.SUCCESS and observation.data.get("not_applicable"):
            fallback = await self._router.route_non_scheduling(state, user_message)
            state.current_focus = fallback.domain
            async for chunk in self._knowledge_answer(state):
                yield chunk
            return

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
            logger.warning("blocked unsafe streamed output reason=%s workflow=%s", exc.reason, state.active_workflow.value if state.active_workflow else "none")
            fallback = self._renderer.safety_fallback(state)
            if emitted:
                fallback = f" {fallback}"
            emitted.append(fallback)
            yield fallback

        text = "".join(emitted)
        if not text.strip():
            text = self._renderer.safety_fallback(state)
            yield text
        await self._sessions.append_turn(state, "assistant", text)

        verification = self._verifier.verify_business_response(state, text)
        if not verification.ok:
            logger.warning("post-stream verification issues=%s workflow=%s", verification.issues, state.active_workflow.value if state.active_workflow else "none")
