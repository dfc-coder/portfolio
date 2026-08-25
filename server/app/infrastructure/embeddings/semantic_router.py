from __future__ import annotations

import asyncio
from typing import Any

from pydantic import ConfigDict
from semantic_router.encoders import DenseEncoder
from semantic_router.encoders.base import AsymmetricDenseMixin

from app.ports.embeddings import EmbeddingPort


class EmbeddingPortEncoder(DenseEncoder, AsymmetricDenseMixin):
    """Expose the existing llama.cpp embedding port to semantic-router.

    Runtime routing stays fully async. Route utterances are encoded as documents and
    visitor messages are encoded as queries, preserving Qwen's asymmetric retrieval
    convention without loading another embedding model in Python.
    """

    embeddings: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __call__(self, docs: list[Any]) -> list[list[float]]:
        raise RuntimeError("Synchronous semantic routing is disabled in the API runtime")

    async def acall(self, docs: list[Any]) -> list[list[float]]:
        return await self.aencode_documents([str(doc) for doc in docs])

    def encode_queries(self, docs: list[str]) -> list[list[float]]:
        raise RuntimeError("Synchronous semantic routing is disabled in the API runtime")

    def encode_documents(self, docs: list[str]) -> list[list[float]]:
        raise RuntimeError("Synchronous semantic routing is disabled in the API runtime")

    async def aencode_queries(self, docs: list[str]) -> list[list[float]]:
        port: EmbeddingPort = self.embeddings
        return list(await asyncio.gather(*(port.embed_query(text) for text in docs)))

    async def aencode_documents(self, docs: list[str]) -> list[list[float]]:
        port: EmbeddingPort = self.embeddings
        return await port.embed_documents(docs)
