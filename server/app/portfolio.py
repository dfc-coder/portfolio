from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from typing import Any

from openai import AsyncOpenAI

Profile = dict[str, Any]
Fact = tuple[str, str]

_QUERY_PREFIX = (
    "Instruct: Given a visitor question about a professional portfolio, retrieve specific portfolio "
    "passages that provide direct evidence needed to answer it.\nQuery: "
)
_RRF_K = 20
_MIN_RANK_WINDOW = 12
_BM25_K1 = 1.2
_BM25_B = 0.75

_STOPWORDS = {
    "a",
    "al",
    "an",
    "and",
    "are",
    "con",
    "de",
    "del",
    "did",
    "do",
    "does",
    "el",
    "en",
    "es",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "la",
    "las",
    "lo",
    "los",
    "of",
    "on",
    "or",
    "para",
    "por",
    "que",
    "se",
    "su",
    "sus",
    "the",
    "their",
    "tiene",
    "un",
    "una",
    "what",
    "which",
    "with",
    "y",
}


class Portfolio:
    def __init__(
        self,
        profile: Profile,
        embeddings: AsyncOpenAI,
        *,
        model: str,
        max_chars: int = 4000,
        max_documents: int = 4,
        min_score: float = 0.10,
    ) -> None:
        self._embeddings = embeddings
        self._model = model
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._min_score = min_score
        self._documents = self._build_documents(profile)
        self._vectors: list[list[float]] | None = None

        self._lexical_documents = [
            Counter(self._tokens(self._search_text(source, text)))
            for source, text in self._documents
        ]
        self._document_frequency: Counter[str] = Counter()
        for terms in self._lexical_documents:
            self._document_frequency.update(terms.keys())
        total_terms = sum(sum(terms.values()) for terms in self._lexical_documents)
        self._avg_document_length = total_terms / max(len(self._lexical_documents), 1)

    async def warm(self) -> None:
        if self._vectors is None:
            self._vectors = await self._embed(
                [self._search_text(source, text) for source, text in self._documents]
            )

    async def search(self, query: str) -> list[dict[str, str]]:
        await self.warm()

        vectors = self._vectors
        if vectors is None:
            raise RuntimeError("portfolio vectors are not initialized")

        query = query.strip()
        query_vector = (await self._embed([f"{_QUERY_PREFIX}{query}"]))[0]
        query_terms = {
            term
            for term in self._tokens(query)
            if term not in _STOPWORDS
        }

        semantic_scores = [
            self._cosine(query_vector, vector)
            for vector in vectors
        ]
        lexical_scores = [
            self._bm25(query_terms, document_terms)
            for document_terms in self._lexical_documents
        ]
        ranked_indices = self._fused_ranking(semantic_scores, lexical_scores)

        facts: list[dict[str, str]] = []
        chars = 0
        for index in ranked_indices:
            if len(facts) >= self._max_documents:
                break

            if lexical_scores[index] <= 0 and semantic_scores[index] < self._min_score:
                continue

            source, text = self._documents[index]
            if facts and chars + len(text) > self._max_chars:
                continue
            facts.append({"source": source, "text": text})
            chars += len(text)

        return facts

    def _bm25(self, query_terms: set[str], document_terms: Counter[str]) -> float:
        if not query_terms or not document_terms or not self._documents:
            return 0.0

        document_length = sum(document_terms.values())
        average_length = self._avg_document_length or 1.0
        document_count = len(self._documents)
        score = 0.0

        for term in query_terms:
            frequency = document_terms.get(term, 0)
            if frequency <= 0:
                continue

            document_frequency = self._document_frequency.get(term, 0)
            idf = math.log(
                1.0
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            normalization = frequency + _BM25_K1 * (
                1.0 - _BM25_B + _BM25_B * document_length / average_length
            )
            score += idf * (frequency * (_BM25_K1 + 1.0)) / normalization

        return score

    def _fused_ranking(
        self,
        semantic_scores: list[float],
        lexical_scores: list[float],
    ) -> list[int]:
        if not semantic_scores:
            return []

        window = min(
            len(semantic_scores),
            max(_MIN_RANK_WINDOW, self._max_documents * 4),
        )
        semantic_order = sorted(
            range(len(semantic_scores)),
            key=lambda index: semantic_scores[index],
            reverse=True,
        )[:window]
        lexical_order = [
            index
            for index in sorted(
                range(len(lexical_scores)),
                key=lambda index: lexical_scores[index],
                reverse=True,
            )
            if lexical_scores[index] > 0
        ][:window]

        semantic_rank = {index: rank for rank, index in enumerate(semantic_order, start=1)}
        lexical_rank = {index: rank for rank, index in enumerate(lexical_order, start=1)}
        candidates = set(semantic_order) | set(lexical_order)

        def rrf(index: int) -> float:
            score = 0.0
            if index in semantic_rank:
                score += 1.0 / (_RRF_K + semantic_rank[index])
            if index in lexical_rank:
                score += 1.0 / (_RRF_K + lexical_rank[index])
            return score

        return sorted(
            candidates,
            key=lambda index: (
                rrf(index),
                lexical_scores[index],
                semantic_scores[index],
            ),
            reverse=True,
        )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._embeddings.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    @staticmethod
    def _build_documents(profile: Profile) -> list[Fact]:
        documents: list[Fact] = []
        for section, value in profile.items():
            if isinstance(value, list):
                documents.extend(
                    (f"{section}.{index}", json.dumps(item, ensure_ascii=False))
                    for index, item in enumerate(value)
                )
                continue

            if isinstance(value, dict):
                documents.extend(
                    (f"{section}.{key}", json.dumps(item, ensure_ascii=False))
                    for key, item in value.items()
                )
                continue

            documents.append((section, json.dumps(value, ensure_ascii=False)))
        return documents

    @staticmethod
    def _search_text(source: str, text: str) -> str:
        label = re.sub(r"[._]+", " ", source)
        return f"{label}\n{text}"

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", text.casefold())
            if unicodedata.category(character) != "Mn"
        )
        return [
            term
            for term in re.findall(r"[\w.+#-]+", normalized)
            if len(term) >= 2
        ]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
