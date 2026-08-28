from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class EmbeddingTask(StrEnum):
    ROUTING = "routing"
    RETRIEVAL = "retrieval"


class EmbeddingPort(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(
        self,
        text: str,
        task: EmbeddingTask,
    ) -> list[float]: ...

    async def health(self) -> bool: ...
