from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from .embeddings import Embeddings
from .profile import Profile


@dataclass(frozen=True)
class Fact:
    source: str
    text: str


class PortfolioSearch:
    def __init__(
        self,
        profile: Profile,
        embeddings: Embeddings,
        *,
        max_chars: int = 4000,
        max_documents: int = 4,
        min_score: float = 0.10,
    ) -> None:
        self._embeddings = embeddings
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._min_score = min_score
        self._documents = self._build_documents(profile)
        self._vectors: list[list[float]] | None = None

    async def warm(self) -> None:
        if self._vectors is None:
            self._vectors = await self._embeddings.documents(
                [text for _, text in self._documents]
            )

    async def search(self, query: str) -> tuple[Fact, ...]:
        await self.warm()
        assert self._vectors is not None
        query_vector = await self._embeddings.query(query)
        ranked = sorted(
            (
                (self._cosine(query_vector, vector), source, text)
                for (source, text), vector in zip(self._documents, self._vectors, strict=True)
            ),
            reverse=True,
        )

        facts: list[Fact] = []
        chars = 0
        for score, source, text in ranked:
            if score < self._min_score or len(facts) >= self._max_documents:
                break
            if facts and chars + len(text) > self._max_chars:
                break
            facts.append(Fact(source=source, text=text))
            chars += len(text)
        return tuple(facts)

    @staticmethod
    def _build_documents(profile: Profile) -> list[tuple[str, str]]:
        documents: list[tuple[str, str]] = []
        for section, value in profile.items():
            if isinstance(value, list):
                for index, item in enumerate(value):
                    documents.append(
                        (f"{section}.{index}", json.dumps(item, ensure_ascii=False))
                    )
            else:
                documents.append((section, json.dumps(value, ensure_ascii=False)))
        return documents

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
