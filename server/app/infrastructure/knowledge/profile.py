from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.domain.profile import BusinessProfile
from app.infrastructure.embeddings.similarity import cosine_similarity
from app.ports.embeddings import EmbeddingPort, EmbeddingTask


@dataclass(frozen=True)
class ProfileDocument:
    document_id: str
    text: str


@dataclass(frozen=True)
class RetrievedDocument:
    document: ProfileDocument
    score: float


class ProfileDocumentIndex:
    """Flatten structured profile data into small retrievable units."""

    def __init__(self, profile: BusinessProfile) -> None:
        self.documents = tuple(self._build(profile))

    @classmethod
    def _build(cls, profile: BusinessProfile) -> list[ProfileDocument]:
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

        add("skills", {"skills": profile.skills.model_dump()})

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

        add("business", {"business": profile.business.model_dump()})
        for index, item in enumerate(profile.faq):
            add(f"faq.{index}", {"faq": item.model_dump()})

        return documents


class ProfileRetriever:
    """Dense profile retrieval with a cached document index."""

    def __init__(
        self,
        index: ProfileDocumentIndex,
        embeddings: EmbeddingPort,
        *,
        max_chars: int = 4000,
        max_documents: int = 4,
    ) -> None:
        self._index = index
        self._embeddings = embeddings
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._document_vectors: list[list[float]] | None = None
        self._index_lock = asyncio.Lock()

    async def warm(self) -> None:
        await self._ensure_index()

    async def search(self, query: str) -> tuple[RetrievedDocument, ...]:
        documents = self._index.documents
        if not documents or not query.strip():
            return ()

        await self._ensure_index()
        if self._document_vectors is None:
            return ()

        query_vector = await self._embeddings.embed_query(
            query,
            EmbeddingTask.RETRIEVAL,
        )
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

        selected: list[RetrievedDocument] = []
        used_chars = 0
        for item in ranked:
            if len(selected) >= self._max_documents:
                break
            size = len(item.document.text)
            if selected and used_chars + size > self._max_chars:
                continue
            if not selected and size > self._max_chars:
                continue
            selected.append(item)
            used_chars += size
            if used_chars >= self._max_chars:
                break
        return tuple(selected)

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
