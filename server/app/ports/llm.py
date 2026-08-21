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


class LlmPort(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str: ...

    async def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]: ...

    async def health(self) -> bool: ...
