from __future__ import annotations

from dataclasses import dataclass

from app.domain.profile import BusinessProfile
from app.infrastructure.knowledge.profile import ProfileDocumentIndex, ProfileRetriever
from app.ports.embeddings import EmbeddingPort


@dataclass(frozen=True)
class Fact:
    text: str
    source: str


@dataclass(frozen=True)
class SearchResult:
    facts: tuple[Fact, ...]


class PortfolioSearch:
    """Stable business capability for retrieving grounded portfolio facts."""

    def __init__(
        self,
        profile: BusinessProfile,
        embeddings: EmbeddingPort,
        *,
        max_chars: int = 4000,
        max_documents: int = 4,
        min_score: float = 0.10,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        self._min_score = min_score
        self._retriever = ProfileRetriever(
            ProfileDocumentIndex(profile),
            embeddings,
            max_chars=max_chars,
            max_documents=max_documents,
        )

    async def warm(self) -> None:
        await self._retriever.warm()

    async def search(self, query: str) -> SearchResult:
        matches = await self._retriever.search(query)
        return SearchResult(
            facts=tuple(
                Fact(
                    text=item.document.text,
                    source=item.document.document_id,
                )
                for item in matches
                if item.score >= self._min_score
            )
        )
