from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient


@pytest.mark.asyncio
async def test_query_embedding_uses_instruction_format() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.3, 0.4]}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        embeddings = LlamaCppEmbeddingClient(
            "http://embedding:8081",
            "Qwen3-Embedding-0.6B",
            client=client,
        )
        vector = await embeddings.embed_query("Contame sobre PocketTrace")

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "Qwen3-Embedding-0.6B"
    assert payload["input"] == [
        "Instruct: Retrieve the text that best matches the visitor's intent.\n"
        "Query: Contame sobre PocketTrace"
    ]
    assert vector == [0.3, 0.4]


@pytest.mark.asyncio
async def test_document_embeddings_are_sent_without_query_instruction() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [1.0, 0.0]},
                    {"index": 1, "embedding": [0.0, 1.0]},
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        embeddings = LlamaCppEmbeddingClient(
            "http://embedding:8081",
            "Qwen3-Embedding-0.6B",
            client=client,
        )
        vectors = await embeddings.embed_documents(["PocketTrace", "Xarlatan"])

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["input"] == ["PocketTrace", "Xarlatan"]
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
