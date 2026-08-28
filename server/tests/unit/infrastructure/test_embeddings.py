from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.ports.embeddings import EmbeddingTask


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task", "expected_instruction"),
    [
        (
            EmbeddingTask.ROUTING,
            "Given a visitor message, retrieve the intent description that best matches "
            "what the visitor wants to do.",
        ),
        (
            EmbeddingTask.RETRIEVAL,
            "Given a visitor question about a professional portfolio, retrieve profile passages "
            "containing the facts needed to answer it.",
        ),
    ],
)
async def test_query_embedding_uses_task_specific_instruction(
    task: EmbeddingTask,
    expected_instruction: str,
) -> None:
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
        vector = await embeddings.embed_query("  Contame sobre PocketTrace  ", task)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "Qwen3-Embedding-0.6B"
    assert payload["input"] == [
        f"Instruct: {expected_instruction}\nQuery: Contame sobre PocketTrace"
    ]
    assert vector == [0.3, 0.4]


@pytest.mark.asyncio
async def test_same_query_uses_different_instructions_for_routing_and_retrieval() -> None:
    captured: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
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
        query = "Quiero hablar con Diego sobre AWS"
        await embeddings.embed_query(query, EmbeddingTask.ROUTING)
        await embeddings.embed_query(query, EmbeddingTask.RETRIEVAL)

    routing_input = captured[0]["input"][0]  # type: ignore[index]
    retrieval_input = captured[1]["input"][0]  # type: ignore[index]
    assert routing_input != retrieval_input
    assert str(routing_input).endswith(f"Query: {query}")
    assert str(retrieval_input).endswith(f"Query: {query}")


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
