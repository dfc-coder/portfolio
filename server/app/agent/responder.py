from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.conversation import SessionState
from app.domain.profile import BusinessProfile
from app.ports.embeddings import EmbeddingPort
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy

from .context import ContextAssembler, ProfileDocumentIndex, ProfileRetriever
from .stream_guard import StreamGuard, UnsafeStreamOutput

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace

logger = logging.getLogger(__name__)


class Responder:
    def __init__(
        self,
        llm: LlmPort,
        profile: BusinessProfile,
        policy: SchedulingPolicy,
        config: GenerationConfig,
        capabilities: tuple[str, ...],
        embeddings: EmbeddingPort,
        *,
        context_max_chars: int = 4000,
        context_max_documents: int = 4,
    ) -> None:
        del policy  # Timezone/policy data is already represented in BusinessProfile.
        self._llm = llm
        self._config = config
        index = ProfileDocumentIndex(profile)
        retriever = ProfileRetriever(
            index,
            embeddings,
            max_chars=context_max_chars,
            max_documents=context_max_documents,
        )
        self._context = ContextAssembler(profile, capabilities, retriever)

    async def stream(
        self,
        state: SessionState,
        trace: TurnTrace | None = None,
    ) -> AsyncIterator[str]:
        guard = StreamGuard()
        emitted = False
        context = await self._context.build(state, trace)
        messages = context.messages()
        raw_chunks: list[str] = []
        visible_chunks: list[str] = []
        unsafe_reason: str | None = None
        fallback_reason: str | None = None
        guard_duration_ms = 0.0
        generation_started = time.perf_counter()

        try:
            async for chunk in self._llm.stream(messages, self._config):
                raw_chunks.append(chunk)
                guard_started = time.perf_counter()
                try:
                    ready = guard.feed(chunk)
                finally:
                    guard_duration_ms += (time.perf_counter() - guard_started) * 1000
                if ready:
                    emitted = True
                    visible_chunks.append(ready)
                    yield ready

            guard_started = time.perf_counter()
            try:
                tail = guard.finish()
            finally:
                guard_duration_ms += (time.perf_counter() - guard_started) * 1000
            if tail:
                emitted = True
                visible_chunks.append(tail)
                yield tail
        except UnsafeStreamOutput as exc:
            unsafe_reason = exc.reason
            fallback_reason = "unsafe_output"
            logger.warning("blocked unsafe streamed output reason=%s", exc.reason)
            fallback = self._fallback(state)
            visible = f" {fallback}" if emitted else fallback
            visible_chunks.append(visible)
            yield visible
            emitted = True
        except Exception as exc:
            if trace is not None:
                trace.add_span(
                    "qwen_generation",
                    (time.perf_counter() - generation_started) * 1000,
                    input={
                        "messages": messages,
                        "config": self._generation_config_payload(),
                    },
                    output={"raw_text": "".join(raw_chunks)},
                    status="failed",
                    error={"kind": type(exc).__name__, "message": str(exc)[:2000]},
                )
                trace.add_span(
                    "stream_guard",
                    guard_duration_ms,
                    input={"raw_text": "".join(raw_chunks)},
                    output={"accepted": None, "visible_text": "".join(visible_chunks)},
                    status="failed",
                    error={"kind": "generation_error", "message": "generation did not complete"},
                )
            raise

        if not emitted:
            fallback_reason = "empty_output"
            fallback = self._fallback(state)
            visible_chunks.append(fallback)
            yield fallback

        if trace is not None:
            trace.add_span(
                "qwen_generation",
                (time.perf_counter() - generation_started) * 1000,
                input={
                    "messages": messages,
                    "config": self._generation_config_payload(),
                },
                output={"raw_text": "".join(raw_chunks)},
            )
            trace.add_span(
                "stream_guard",
                guard_duration_ms,
                input={"raw_text": "".join(raw_chunks)},
                output={
                    "accepted": unsafe_reason is None,
                    "visible_text": "".join(visible_chunks),
                    "fallback_reason": fallback_reason,
                },
                status="failed" if unsafe_reason is not None else "ok",
                error=(
                    {"kind": "unsafe_output", "message": unsafe_reason}
                    if unsafe_reason is not None
                    else None
                ),
            )

    def _generation_config_payload(self) -> dict[str, float | int | None]:
        return {
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "top_p": self._config.top_p,
            "top_k": self._config.top_k,
            "presence_penalty": self._config.presence_penalty,
        }

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
