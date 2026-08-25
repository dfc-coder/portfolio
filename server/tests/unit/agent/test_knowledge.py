from __future__ import annotations

import pytest

from app.agent.knowledge import ProfileDocumentIndex, ProfileRetriever
from app.domain.profile import BusinessProfile


class ControlledEmbeddings:
    def __init__(self, target: str | None = None, unrelated: bool = False) -> None:
        self.target = target
        self.unrelated = unrelated
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        vectors: list[list[float]] = []
        for text in texts:
            if self.target and self.target in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [0.0, -1.0] if self.unrelated else [1.0, 0.0]

    async def health(self) -> bool:
        return True


def test_profile_index_is_generated_as_natural_language_chunks(
    profile: BusinessProfile,
) -> None:
    index = ProfileDocumentIndex(
        profile,
        ("Check calendar availability.",),
    )
    ids = {document.document_id for document in index.documents}

    assert "owner" in ids
    assert "positioning" in ids
    assert "skills.programming_languages" in ids
    assert "representative.capabilities" not in ids
    assert any(value.startswith("experience.") for value in ids)
    assert any(value.startswith("professional_experience.") for value in ids)
    assert any(value.startswith("projects.") for value in ids)
    assert any(value.startswith("faq.") for value in ids)
    assert all(not document.text.lstrip().startswith("{") for document in index.documents)


@pytest.mark.asyncio
async def test_experience_query_is_driven_by_profile_documents(
    profile: BusinessProfile,
) -> None:
    embeddings = ControlledEmbeddings(target="Professional experience.")
    retriever = ProfileRetriever(
        ProfileDocumentIndex(profile),
        embeddings,
        min_score=0.25,
        max_documents=2,
    )

    result = await retriever.search(
        "Quiero información sobre la experiencia profesional de Diego"
    )

    assert result.matched is True
    assert result.top_score == pytest.approx(1.0)
    assert any(
        item.document.document_id.startswith("professional_experience.")
        for item in result.documents
    )


@pytest.mark.asyncio
async def test_irrelevant_query_returns_no_portfolio_context(
    profile: BusinessProfile,
) -> None:
    embeddings = ControlledEmbeddings(unrelated=True)
    retriever = ProfileRetriever(
        ProfileDocumentIndex(profile),
        embeddings,
        min_score=0.25,
    )

    result = await retriever.search("¿Qué hora es?")

    assert result.matched is False
    assert result.documents == ()
    assert result.top_score <= 0.0


@pytest.mark.asyncio
async def test_profile_vectors_are_computed_once(
    profile: BusinessProfile,
) -> None:
    embeddings = ControlledEmbeddings(target="PocketTrace")
    retriever = ProfileRetriever(
        ProfileDocumentIndex(profile),
        embeddings,
        min_score=0.25,
    )

    await retriever.search("PocketTrace")
    await retriever.search("PocketTrace")

    assert len(embeddings.document_calls) == 1
    assert len(embeddings.query_calls) == 2
