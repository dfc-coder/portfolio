from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.ports.llm import GenerationConfig


def _sse(*payloads: dict[str, object] | str) -> bytes:
    lines: list[str] = []
    for payload in payloads:
        data = payload if isinstance(payload, str) else json.dumps(payload)
        lines.append(f"data: {data}\n\n")
    return "".join(lines).encode()


@pytest.mark.asyncio
async def test_stream_preserves_text_and_captures_terminal_metadata() -> None:
    captured_request: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_request.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=_sse(
                {
                    "choices": [{"delta": {"content": "Hola "}, "finish_reason": None}],
                    "system_fingerprint": "llama-build-a",
                },
                {"choices": [{"delta": {"content": "mundo"}, "finish_reason": None}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 2,
                        "total_tokens": 102,
                        "prompt_tokens_details": {"cached_tokens": 80},
                    },
                    "timings": {
                        "cache_n": 80,
                        "prompt_n": 20,
                        "prompt_ms": 10.5,
                        "prompt_per_token_ms": 0.525,
                        "prompt_per_second": 1904.76,
                        "predicted_n": 2,
                        "predicted_ms": 50.0,
                        "predicted_per_token_ms": 25.0,
                        "predicted_per_second": 40.0,
                    },
                },
                "[DONE]",
            ),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = LlamaCppClient(
            "http://llama:8080",
            "Qwen3.5-2B",
            client=http_client,
        )
        generation = client.stream(
            [{"role": "user", "content": "hola"}],
            GenerationConfig(temperature=0.65, max_tokens=180),
        )
        text = "".join([chunk async for chunk in generation])

    assert text == "Hola mundo"
    assert captured_request["stream_options"] == {"include_usage": True}
    assert generation.metadata.finish_reason == "stop"
    assert generation.metadata.system_fingerprint == "llama-build-a"
    assert generation.metadata.usage is not None
    assert generation.metadata.usage.prompt_tokens == 100
    assert generation.metadata.usage.completion_tokens == 2
    assert generation.metadata.usage.total_tokens == 102
    assert generation.metadata.usage.cached_tokens == 80
    assert generation.metadata.timings is not None
    assert generation.metadata.timings.cache_n == 80
    assert generation.metadata.timings.prompt_n == 20
    assert generation.metadata.timings.prompt_ms == 10.5
    assert generation.metadata.timings.predicted_n == 2
    assert generation.metadata.timings.predicted_ms == 50.0
    assert generation.metadata.timings.predicted_per_second == 40.0


@pytest.mark.asyncio
async def test_stream_captures_length_without_fabricating_missing_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                {"choices": [{"delta": {"content": "cortado"}}]},
                {"choices": [{"delta": {"finish_reason": "length"}}]},
                "[DONE]",
            ),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = LlamaCppClient("http://llama:8080", "Qwen3.5-2B", client=http_client)
        generation = client.stream(
            [{"role": "user", "content": "explicame"}],
            GenerationConfig(temperature=0.65, max_tokens=1),
        )
        text = "".join([chunk async for chunk in generation])

    assert text == "cortado"
    assert generation.metadata.finish_reason == "length"
    assert generation.metadata.usage is None
    assert generation.metadata.timings is None
    assert generation.metadata.system_fingerprint is None


class _FailingStream(httpx.AsyncByteStream):
    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield _sse(
            {
                "choices": [{"delta": {"content": "partial"}}],
                "system_fingerprint": "llama-build-before-failure",
            }
        )
        raise httpx.ReadError("stream interrupted")


@pytest.mark.asyncio
async def test_partial_metadata_survives_transport_failure_without_finish_reason() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_FailingStream(), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = LlamaCppClient("http://llama:8080", "Qwen3.5-2B", client=http_client)
        generation = client.stream(
            [{"role": "user", "content": "hola"}],
            GenerationConfig(temperature=0.65, max_tokens=180),
        )

        with pytest.raises(httpx.ReadError, match="stream interrupted"):
            _ = [chunk async for chunk in generation]

    assert generation.metadata.system_fingerprint == "llama-build-before-failure"
    assert generation.metadata.finish_reason is None
    assert generation.metadata.usage is None
