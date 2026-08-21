from __future__ import annotations

from typing import Protocol


class RerankerPort(Protocol):
    async def rerank(self, query: str, documents: list[str]) -> list[float]: ...

    async def health(self) -> bool: ...
