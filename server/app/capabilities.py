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
    "Classify the CURRENT visitor request by intent. Recent conversation is only context for abbreviated "
    "follow-ups. Match what the visitor wants the assistant to do, not nouns mentioned inside the request."
)


@dataclass(frozen=True)
class _Route:
    name: str
    capabilities: tuple[str, ...]
    requires_tool: bool
    description: str


_ROUTES = (
    _Route(
        "conversation",
        (),
        False,
        "Ordinary conversation or general knowledge that needs no portfolio evidence, deterministic time "
        "calculation, or external action: greetings, thanks, jokes, definitions and casual questions.",
    ),
    _Route(
        "portfolio",
        (CAPABILITY_PORTFOLIO,),
        True,
        "A factual question asking to KNOW something about Diego or the portfolio subject: professional "
        "background, experience, skills, projects, education, certifications, services or technical work. "
        "This is information retrieval, not an instruction to perform an action on a portfolio, CV or task.",
    ),
    _Route(
        "datetime",
        (CAPABILITY_DATETIME,),
        True,
        "A question asking to CALCULATE or RESOLVE a date, time, weekday, relative date or calendar offset. "
        "It asks what date/time something is; it does not ask the assistant to create a reminder or action.",
    ),
    _Route(
        "reminder",
        (CAPABILITY_REMINDER,),
        True,
        "An ACTION request asking the assistant to create or change a reminder for the visitor. The content "
        "of the reminder may mention a portfolio, CV, application, project or any other subject; classify by "
        "the requested reminder action, not by the reminder text.",
    ),
)


@dataclass(frozen=True)
class CapabilityDecision:
    names: tuple[str, ...]
    latency_ms: float
    route: str | None = None
    requires_tool: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None

    def trace(self) -> dict[str, Any]:
        return {
            "eligible": list(self.names),
            "route": self.route,
            "requires_tool": self.requires_tool,
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
    """Select one exact production capability with the existing embedding model."""

    def __init__(self, embeddings: AsyncOpenAI, *, model: str) -> None:
        self._embeddings = embeddings
        self._model = model
        self._route_vectors: list[list[float]] | None = None

    async def warm(self) -> None:
        if self._route_vectors is None:
            self._route_vectors = await self._embed([route.description for route in _ROUTES])

    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> CapabilityDecision:
        started = time.perf_counter()
        await self.warm()
        assert self._route_vectors is not None

        query = f"Instruct: {_ROUTING_INSTRUCTION}\nQuery: {_routing_input(message, context)}"
        query_vector = (await self._embed([query]))[0]
        scores = [_cosine(query_vector, vector) for vector in self._route_vectors]
        best_index = max(range(len(_ROUTES)), key=scores.__getitem__)
        route = _ROUTES[best_index]

        requires_tool = route.requires_tool
        if context and route.name in {"portfolio", "datetime"}:
            requires_tool = False

        return CapabilityDecision(
            names=route.capabilities,
            route=route.name,
            requires_tool=requires_tool,
            scores={
                candidate.name: round(score, 6)
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


def _routing_input(message: str, context: list[dict[str, Any]]) -> str:
    recent: list[str] = []
    for item in context[-4:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        recent.append(f"{role}: {content.strip()}")

    if not recent:
        return message.strip()

    return "\n".join(
        [
            "Recent conversation:",
            *recent,
            "Current visitor message:",
            message.strip(),
        ]
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
