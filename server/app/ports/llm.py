from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    max_tokens: int
    top_p: float | None = None
    top_k: int | None = None
    presence_penalty: float | None = None


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None


@dataclass(frozen=True)
class GenerationTimings:
    cache_n: int | None = None
    prompt_n: int | None = None
    prompt_ms: float | None = None
    prompt_per_token_ms: float | None = None
    prompt_per_second: float | None = None
    predicted_n: int | None = None
    predicted_ms: float | None = None
    predicted_per_token_ms: float | None = None
    predicted_per_second: float | None = None


@dataclass(frozen=True)
class GenerationMetadata:
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    timings: GenerationTimings | None = None
    system_fingerprint: str | None = None


class GenerationStream(Protocol):
    @property
    def metadata(self) -> GenerationMetadata: ...

    def __aiter__(self) -> AsyncIterator[str]: ...


class LlmPort(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str: ...

    def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> GenerationStream: ...

    async def health(self) -> bool: ...
