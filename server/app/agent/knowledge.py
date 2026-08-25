from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.domain.profile import BusinessProfile
from app.ports.embeddings import EmbeddingPort

from .similarity import cosine_similarity


@dataclass(frozen=True)
class ProfileDocument:
    document_id: str
    text: str


@dataclass(frozen=True)
class RetrievedDocument:
    document: ProfileDocument
    score: float


@dataclass(frozen=True)
class KnowledgeSearch:
    documents: tuple[RetrievedDocument, ...]
    top_score: float
    threshold: float

    @property
    def matched(self) -> bool:
        return bool(self.documents)


class ProfileDocumentIndex:
    """Static portfolio knowledge transformed into retrievable documents."""

    def __init__(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...] = (),
    ) -> None:
        self.documents = tuple(self._build(profile, capabilities))

    @classmethod
    def _build(
        cls,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
    ) -> list[ProfileDocument]:
        documents: list[ProfileDocument] = []

        def add(document_id: str, payload: object) -> None:
            documents.append(
                ProfileDocument(
                    document_id=document_id,
                    text=json.dumps(payload, ensure_ascii=False),
                )
            )

        add("owner", {"owner": profile.owner.model_dump()})
        add("positioning", {"positioning": profile.positioning.model_dump()})

        for index, item in enumerate(profile.experience):
            add(f"experience.{index}", {"experience": item.model_dump()})
        for index, item in enumerate(profile.professional_experience):
            add(
                f"professional_experience.{index}",
                {"professional_experience": item.model_dump()},
            )

        for field_name, values in profile.skills.model_dump().items():
            if values:
                add(f"skills.{field_name}", {"skills": {field_name: values}})

        for index, item in enumerate(profile.services):
            add(f"services.{index}", {"service": item.model_dump()})
        for index, item in enumerate(profile.projects):
            add(f"projects.{index}", {"project": item.model_dump()})
        for index, item in enumerate(profile.education):
            add(f"education.{index}", {"education": item.model_dump()})
        for index, item in enumerate(profile.certifications):
            add(f"certifications.{index}", {"certification": item.model_dump()})
        for index, item in enumerate(profile.languages):
            add(f"languages.{index}", {"language": item.model_dump()})

        business = profile.business
        if business.collaboration_modes:
            add(
                "business.collaboration_modes",
                {"collaboration_modes": business.collaboration_modes},
            )
        if business.project_types:
            add("business.project_types", {"project_types": business.project_types})
        if business.geographic_scope:
            add(
                "business.geographic_scope",
                {"geographic_scope": business.geographic_scope},
            )
        if business.boundaries:
            add("business.boundaries", {"boundaries": business.boundaries})

        if capabilities:
            add("representative.capabilities", {"capabilities": list(capabilities)})

        return documents


class ProfileRetriever:
    """Dense relevance gate: cached portfolio vectors + one query embedding."""

    def __init__(
        self,
        index: ProfileDocumentIndex,
        embeddings: EmbeddingPort,
        *,
        min_score: float = 0.50,
        max_chars: int = 4000,
        max_documents: int = 4,
    ) -> None:
        self._index = index
        self._embeddings = embeddings
        self._min_score = max(0.0, min(1.0, min_score))
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._document_vectors: list[list[float]] | None = None
        self._index_lock = asyncio.Lock()

    @property
    def threshold(self) -> float:
        return self._min_score

    async def warm(self) -> None:
        await self._ensure_index()

    async def search(self, query: str) -> KnowledgeSearch:
        documents = self._index.documents
        if not documents or not query.strip():
            return KnowledgeSearch((), 0.0, self._min_score)

        await self._ensure_index()
        assert self._document_vectors is not None

        query_vector = await self._embeddings.embed_query(query)
        ranked = sorted(
            (
                RetrievedDocument(
                    document=document,
                    score=cosine_similarity(query_vector, vector),
                )
                for document, vector in zip(
                    documents,
                    self._document_vectors,
                    strict=True,
                )
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        top_score = ranked[0].score if ranked else 0.0

        selected: list[RetrievedDocument] = []
        used_chars = 0
        for item in ranked:
            if item.score < self._min_score:
                break
            if len(selected) >= self._max_documents:
                break

            size = len(item.document.text)
            if size > self._max_chars:
                continue
            if selected and used_chars + size > self._max_chars:
                continue

            selected.append(item)
            used_chars += size
            if used_chars >= self._max_chars:
                break

        return KnowledgeSearch(tuple(selected), top_score, self._min_score)

    async def _ensure_index(self) -> None:
        if self._document_vectors is not None:
            return

        async with self._index_lock:
            if self._document_vectors is not None:
                return

            vectors = await self._embeddings.embed_documents(
                [document.text for document in self._index.documents]
            )
            if len(vectors) != len(self._index.documents):
                raise ValueError(
                    "Embedding service returned an unexpected profile vector count"
                )
            self._document_vectors = vectors
