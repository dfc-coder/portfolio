from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.domain.conversation import SessionState
from app.domain.profile import BusinessProfile
from app.ports.llm import GenerationConfig, LlmPort
from app.ports.reranker import RerankerPort
from app.scheduling.policy import SchedulingPolicy

from .context import ContextAssembler, ProfileDocumentIndex, ProfileRetriever
from .stream_guard import StreamGuard, UnsafeStreamOutput

logger = logging.getLogger(__name__)


class Responder:
    def __init__(
        self,
        llm: LlmPort,
        profile: BusinessProfile,
        policy: SchedulingPolicy,
        config: GenerationConfig,
        capabilities: tuple[str, ...],
        reranker: RerankerPort | None = None,
        *,
        context_relevance_threshold: float = 0.10,
        context_max_chars: int = 6000,
        context_max_documents: int = 6,
    ) -> None:
        del policy  # Timezone/policy data is already represented in BusinessProfile.
        self._llm = llm
        self._config = config
        index = ProfileDocumentIndex(profile)
        retriever = ProfileRetriever(
            index,
            reranker,
            min_score=context_relevance_threshold,
            max_chars=context_max_chars,
            max_documents=context_max_documents,
        )
        self._context = ContextAssembler(profile, capabilities, retriever)

    async def stream(self, state: SessionState) -> AsyncIterator[str]:
        guard = StreamGuard()
        emitted = False
        context = await self._context.build(state)
        try:
            async for chunk in self._llm.stream(context.messages(), self._config):
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
            return "No pude generar una respuesta fiable. Probá reformulando la pregunta."
        return "I couldn't generate a reliable answer. Try rephrasing the question."
