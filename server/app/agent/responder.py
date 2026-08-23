from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.domain.conversation import SessionState
from app.domain.profile import BusinessProfile
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy

from .stream_guard import StreamGuard, UnsafeStreamOutput

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are the conversational business representative for the portfolio owner.
Reply in the visitor's language. Be concise and useful.
You are not Diego and must never claim to be him or claim to be human.
Do not introduce yourself as Diego. For ordinary greetings, simply greet the visitor and offer help.
You are the conversational interface of an agent that can use only the actions listed in AGENT_CAPABILITIES.
When asked whether you can use tools or what you can do, describe those capabilities accurately. Do not say the agent cannot use tools when capabilities are listed.
Free-form generated text never executes a side effect. Calendar actions are executed by the scheduler, not by this response generator.
You may describe what the agent can do, but never claim an action already happened unless verified state explicitly says it did.
For owner-specific facts, use only facts explicitly present in BUSINESS_CONTEXT. Do not infer, guess, embellish, or combine facts into unsupported claims.
When BUSINESS_CONTEXT supports the answer, answer directly and prefer concrete project, role or technology names as evidence.
Absence of a fact is not evidence of the opposite. Never answer "no" solely because a fact is missing from BUSINESS_CONTEXT; say the information is not available instead.
Do not invent clients, rates, availability, results, credentials or dates.
Keep normal answers under 120 words unless the visitor asks for detail.
"""


class Responder:
    def __init__(
        self,
        llm: LlmPort,
        profile: BusinessProfile,
        policy: SchedulingPolicy,
        config: GenerationConfig,
        capabilities: tuple[str, ...],
    ) -> None:
        self._llm = llm
        self._profile = profile
        self._policy = policy
        self._config = config
        self._capabilities = capabilities

    async def stream(self, state: SessionState) -> AsyncIterator[str]:
        guard = StreamGuard()
        emitted = False
        try:
            async for chunk in self._llm.stream(self._messages(state), self._config):
                ready = guard.feed(chunk)
                if ready:
                    emitted = True
                    yield ready
            tail = guard.finish()
            if tail:
                emitted = True
                yield tail
        except UnsafeStreamOutput as exc:
            logger.warning("blocked unsafe streamed output reason=%s", exc.reason)
            fallback = self._fallback(state)
            yield f" {fallback}" if emitted else fallback
            emitted = True

        if not emitted:
            yield self._fallback(state)

    def _messages(self, state: SessionState) -> list[dict[str, str]]:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        capabilities = "\n".join(f"- {item}" for item in self._capabilities)
        system = (
            f"{_SYSTEM_PROMPT}\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"TIMEZONE={self._profile.scheduling.timezone}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={state.active_workflow.value if state.active_workflow else 'none'}\n"
            f"LAST_BOOKING_VERIFIED={bool(state.last_booking_id)}\n"
            f"AGENT_CAPABILITIES:\n{capabilities}\n"
            f"BUSINESS_CONTEXT={self._profile.prompt_context()}"
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend({"role": turn.role, "content": turn.content} for turn in state.turns[-4:])
        return messages

    @staticmethod
    def _fallback(state: SessionState) -> str:
        message = state.turns[-1].content.lower() if state.turns else ""
        spanish_tokens = (
            "¿",
            "hola",
            "qué",
            "que ",
            "por qué",
            "porque",
            "puedo",
            "podés",
            "podes",
            "reunión",
            "herramient",
        )
        spanish = any(token in message for token in spanish_tokens) or any(
            char in message for char in "áéíóúñ"
        )
        if spanish:
            return "No puedo afirmar eso sin información verificable en el contexto disponible."
        return "I can't make that claim without verifiable information in the available context."
