from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.agent.responder import Responder
from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import Route
from app.infrastructure.pockettrace import PocketTraceRecorder
from app.ports.llm import (
    GenerationConfig,
    GenerationMetadata,
    GenerationTimings,
    TokenUsage,
)


class FakeGenerationStream:
    def __init__(self) -> None:
        self.metadata = GenerationMetadata(
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=120,
                completion_tokens=2,
                total_tokens=122,
                cached_tokens=90,
            ),
            timings=GenerationTimings(
                cache_n=90,
                prompt_n=30,
                prompt_ms=15.0,
                predicted_n=2,
                predicted_ms=50.0,
                predicted_per_second=40.0,
            ),
            system_fingerprint="llama-build-test",
        )

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[str]:
        yield "Hola "
        yield "mundo"


class FakeLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        return FakeGenerationStream()

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_generation_metadata_reaches_trace_without_changing_visible_stream(
    profile: BusinessProfile,
) -> None:
    responder = Responder(
        FakeLlm(),  # type: ignore[arg-type]
        profile,
        GenerationConfig(temperature=0.65, max_tokens=180),
        (),
    )
    state = SessionState("session-observability", current_focus=Route.CONVERSATION)
    state.turns.append(ChatTurn(role="user", content="hola"))
    trace = PocketTraceRecorder("http://unused:4319", "Qwen3.5-2B").start_turn(
        state.session_id,
        "hola",
    )

    visible = "".join([chunk async for chunk in responder.stream(state, trace)])

    assert visible == "Hola mundo"
    qwen_span = next(span for span in trace.spans if span.name == "qwen_generation")
    assert qwen_span.output["raw_text"] == "Hola mundo"
    assert qwen_span.output["metadata"] == {
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 2,
            "total_tokens": 122,
            "cached_tokens": 90,
        },
        "timings": {
            "cache_n": 90,
            "prompt_n": 30,
            "prompt_ms": 15.0,
            "predicted_n": 2,
            "predicted_ms": 50.0,
            "predicted_per_second": 40.0,
        },
        "system_fingerprint": "llama-build-test",
    }
    guard_span = next(span for span in trace.spans if span.name == "stream_guard")
    assert guard_span.input == {"raw_text": "Hola mundo"}
    assert "metadata" not in guard_span.input
