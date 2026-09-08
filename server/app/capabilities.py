from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

CAPABILITY_PORTFOLIO = "portfolio"
CAPABILITY_DATETIME = "datetime"
CAPABILITY_REMINDER = "reminder"
CAPABILITIES = (
    CAPABILITY_PORTFOLIO,
    CAPABILITY_DATETIME,
    CAPABILITY_REMINDER,
)

_ROUTING_INSTRUCTION = (
    "Given a visitor message, retrieve the intent description that best matches "
    "what the visitor wants to do."
)

_ROUTES = (
    (
        "conversation",
        (),
        "General conversation that does not require external data or an action, such as greetings, "
        "thanks, jokes, definitions, casual chat or general knowledge.",
    ),
    (
        "portfolio",
        (CAPABILITY_PORTFOLIO,),
        "A factual question about the portfolio subject's professional background, experience, skills, "
        "projects, education, certifications, services or technical work.",
    ),
    (
        "temporal",
        (CAPABILITY_DATETIME, CAPABILITY_REMINDER),
        "A request involving deterministic date or time resolution, calendar arithmetic, or creating or "
        "changing a reminder.",
    ),
)


@dataclass(frozen=True)
class CapabilityDecision:
    names: tuple[str, ...]
    latency_ms: float
    route: str | None = None
    scores: dict[str, float] = field(default_factory=dict)
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None

    def trace(self) -> dict[str, Any]:
        return {
            "eligible": list(self.names),
            "route": self.route,
            "scores": self.scores,
            "latency_ms": round(self.latency_ms, 3),
            "finish_reason": self.finish_reason,
            "usage": self.usage,
        }


class CapabilitySelector(Protocol):
    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> CapabilityDecision: ...


class SemanticCapabilitySelector:
    """Select the smallest tool set with the existing embedding model."""

    def __init__(self, embeddings: AsyncOpenAI, *, model: str) -> None:
        self._embeddings = embeddings
        self._model = model
        self._route_vectors: list[list[float]] | None = None

    async def warm(self) -> None:
        if self._route_vectors is None:
            self._route_vectors = await self._embed([route[2] for route in _ROUTES])

    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> CapabilityDecision:
        del context
        started = time.perf_counter()
        await self.warm()
        assert self._route_vectors is not None

        query = f"Instruct: {_ROUTING_INSTRUCTION}\nQuery: {message.strip()}"
        query_vector = (await self._embed([query]))[0]
        scores = [
            _cosine(query_vector, vector)
            for vector in self._route_vectors
        ]
        best_index = max(range(len(_ROUTES)), key=scores.__getitem__)
        route, names, _ = _ROUTES[best_index]

        return CapabilityDecision(
            names=names,
            route=route,
            scores={
                candidate[0]: round(score, 6)
                for candidate, score in zip(_ROUTES, scores, strict=True)
            },
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._embeddings.embeddings.create(
            model=self._model,
            input=texts,
        )
        vectors = [
            item.embedding
            for item in sorted(response.data, key=lambda item: item.index)
        ]
        if len(vectors) != len(texts):
            raise ValueError("embedding service returned an unexpected vector count")
        return vectors


def all_capabilities() -> CapabilityDecision:
    return CapabilityDecision(
        names=CAPABILITIES,
        latency_ms=0.0,
        route="all",
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
