from __future__ import annotations

import pytest

from app.domain.profile import BusinessProfile
from app.ports.embeddings import EmbeddingTask
from app.portfolio.search import PortfolioSearch


class RecordingEmbeddings:
    def __init__(self, target: str | None = None) -> None:
        self.target = target
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []
        self.query_tasks: list[EmbeddingTask] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [
            [1.0, 0.0] if self.target and self.target in text else [0.0, 1.0]
            for text in texts
        ]

    async def embed_query(self, text: str, task: EmbeddingTask) -> list[float]:
        self.query_calls.append(text)
        self.query_tasks.append(task)
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_portfolio_search_returns_concrete_facts(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="PocketTrace")
    search = PortfolioSearch(
        profile,
        embeddings,
        max_chars=6000,
        max_documents=1,
        min_score=0.5,
    )

    result = await search.search("¿Qué proyecto usa Rust para inspeccionar trazas?")

    assert len(result.facts) == 1
    assert result.facts[0].source.startswith("projects.")
    assert "PocketTrace" in result.facts[0].text
    assert embeddings.query_tasks == [EmbeddingTask.RETRIEVAL]


@pytest.mark.asyncio
async def test_portfolio_search_does_not_return_unsupported_fact(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target=None)
    search = PortfolioSearch(
        profile,
        embeddings,
        max_documents=4,
        min_score=0.5,
    )

    result = await search.search("certificación inexistente XYZ-999")

    assert result.facts == ()


@pytest.mark.asyncio
async def test_portfolio_document_embeddings_are_computed_once(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="PocketTrace")
    search = PortfolioSearch(profile, embeddings, min_score=0.0)

    await search.search("PocketTrace")
    await search.search("Rust")

    assert len(embeddings.document_calls) == 1
    assert embeddings.query_calls == ["PocketTrace", "Rust"]
    assert embeddings.query_tasks == [EmbeddingTask.RETRIEVAL, EmbeddingTask.RETRIEVAL]
