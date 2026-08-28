from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx
from pydantic import BaseModel

from app.ports.llm import (
    GenerationConfig,
    GenerationMetadata,
    GenerationStream,
    GenerationTimings,
    TokenUsage,
)


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class _MetadataAccumulator:
    def __init__(self) -> None:
        self.finish_reason: str | None = None
        self.usage: TokenUsage | None = None
        self.timings: GenerationTimings | None = None
        self.system_fingerprint: str | None = None

    def update(self, payload: Mapping[str, Any]) -> None:
        fingerprint = payload.get("system_fingerprint")
        if isinstance(fingerprint, str):
            self.system_fingerprint = fingerprint

        usage = payload.get("usage")
        if isinstance(usage, Mapping):
            prompt_details = usage.get("prompt_tokens_details")
            cached_tokens = usage.get("cached_tokens")
            if cached_tokens is None and isinstance(prompt_details, Mapping):
                cached_tokens = prompt_details.get("cached_tokens")
            parsed_usage = TokenUsage(
                prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                completion_tokens=_optional_int(usage.get("completion_tokens")),
                total_tokens=_optional_int(usage.get("total_tokens")),
                cached_tokens=_optional_int(cached_tokens),
            )
            if any(value is not None for value in vars(parsed_usage).values()):
                self.usage = parsed_usage

        timings = payload.get("timings")
        if isinstance(timings, Mapping):
            parsed_timings = GenerationTimings(
                cache_n=_optional_int(timings.get("cache_n")),
                prompt_n=_optional_int(timings.get("prompt_n")),
                prompt_ms=_optional_float(timings.get("prompt_ms")),
                prompt_per_token_ms=_optional_float(timings.get("prompt_per_token_ms")),
                prompt_per_second=_optional_float(timings.get("prompt_per_second")),
                predicted_n=_optional_int(timings.get("predicted_n")),
                predicted_ms=_optional_float(timings.get("predicted_ms")),
                predicted_per_token_ms=_optional_float(
                    timings.get("predicted_per_token_ms")
                ),
                predicted_per_second=_optional_float(timings.get("predicted_per_second")),
            )
            if any(value is not None for value in vars(parsed_timings).values()):
                self.timings = parsed_timings

        for choice in payload.get("choices") or []:
            if not isinstance(choice, Mapping):
                continue
            delta = choice.get("delta")
            finish_reason = choice.get("finish_reason")
            if finish_reason is None and isinstance(delta, Mapping):
                finish_reason = delta.get("finish_reason")
            if isinstance(finish_reason, str):
                self.finish_reason = finish_reason

    def snapshot(self) -> GenerationMetadata:
        return GenerationMetadata(
            finish_reason=self.finish_reason,
            usage=self.usage,
            timings=self.timings,
            system_fingerprint=self.system_fingerprint,
        )


class _LlamaCppGenerationStream(GenerationStream):
    def __init__(
        self,
        client: httpx.AsyncClient,
        slot: asyncio.Semaphore,
        endpoint: str,
        payload: dict[str, Any],
    ) -> None:
        self._client = client
        self._slot = slot
        self._endpoint = endpoint
        self._payload = payload
        self._metadata = _MetadataAccumulator()
        self._started = False

    @property
    def metadata(self) -> GenerationMetadata:
        return self._metadata.snapshot()

    def __aiter__(self) -> AsyncIterator[str]:
        if self._started:
            raise RuntimeError("Generation stream can only be consumed once")
        self._started = True
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[str]:
        async with self._slot:
            async with self._client.stream(
                "POST",
                self._endpoint,
                json=self._payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break

                    payload = json.loads(data)
                    if not isinstance(payload, dict):
                        continue
                    self._metadata.update(payload)

                    for choice in payload.get("choices") or []:
                        if not isinstance(choice, Mapping):
                            continue
                        delta = choice.get("delta")
                        if not isinstance(delta, Mapping):
                            continue
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield content


class LlamaCppClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 90.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._slot = asyncio.Semaphore(1)

    def _payload(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        *,
        stream: bool,
        response_schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "cache_prompt": True,
            "id_slot": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        if config.top_p is not None:
            payload["top_p"] = config.top_p
        if config.top_k is not None:
            payload["top_k"] = config.top_k
        if config.presence_penalty is not None:
            payload["presence_penalty"] = config.presence_penalty
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            }
        return payload

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        async with self._slot:
            payload = self._payload(
                messages,
                config,
                stream=False,
                response_schema=response_schema,
            )
            response = await self._client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            )
            if response.status_code in {400, 422} and response_schema is not None:
                fallback = dict(payload)
                fallback["response_format"] = {"type": "json_object"}
                response = await self._client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=fallback,
                )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            return message.get("content") or ""

    def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> GenerationStream:
        return _LlamaCppGenerationStream(
            self._client,
            self._slot,
            f"{self._base_url}/v1/chat/completions",
            self._payload(messages, config, stream=True),
        )
