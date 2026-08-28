from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.ports.embeddings import EmbeddingPort, EmbeddingTask

from .similarity import cosine_similarity


@dataclass(frozen=True)
class Route:
    key: str
    domain: RouteDomain
    relation: RouteRelation
    description: str


_NEW_ROUTES = (
    Route(
        "business",
        RouteDomain.BUSINESS,
        RouteRelation.NEW,
        (
            "A visitor asks about Diego's professional background, experience, projects, "
            "technologies, skills, services, credentials, rates, clients or capabilities."
        ),
    ),
    Route(
        "scheduling",
        RouteDomain.SCHEDULING,
        RouteRelation.NEW,
        (
            "A visitor wants to arrange, reschedule or cancel a meeting with Diego, check real "
            "calendar availability, choose a meeting time, or provide meeting details."
        ),
    ),
    Route(
        "general",
        RouteDomain.GENERAL,
        RouteRelation.NEW,
        (
            "A greeting, small talk, casual conversation, or a question unrelated to Diego's "
            "professional profile and unrelated to arranging a meeting."
        ),
    ),
)

_ACTIVE_SCHEDULING_ROUTES = (
    Route(
        "business_interrupt",
        RouteDomain.BUSINESS,
        RouteRelation.INTERRUPT,
        (
            "A professional question about Diego's work, projects, technologies, experience, "
            "skills, services or credentials while a meeting workflow is already active."
        ),
    ),
    Route(
        "scheduling_continue",
        RouteDomain.SCHEDULING,
        RouteRelation.CONTINUE,
        (
            "A continuation of the active meeting workflow, such as providing a date, email, "
            "meeting subject, selecting a proposed slot, changing a time, or cancelling it."
        ),
    ),
    Route(
        "general_interrupt",
        RouteDomain.GENERAL,
        RouteRelation.INTERRUPT,
        (
            "A greeting, small talk or unrelated conversation while a meeting workflow is active. "
            "The existing meeting state must be preserved."
        ),
    ),
)

_FALLBACK_ROUTES = (
    Route(
        "business_fallback",
        RouteDomain.BUSINESS,
        RouteRelation.NEW,
        _NEW_ROUTES[0].description,
    ),
    Route(
        "general_fallback",
        RouteDomain.GENERAL,
        RouteRelation.NEW,
        _NEW_ROUTES[2].description,
    ),
)


class SemanticRouter:
    """Three-way semantic routing using the same dense embeddings as profile retrieval."""

    def __init__(self, embeddings: EmbeddingPort) -> None:
        self._embeddings = embeddings
        self._route_vectors: dict[str, list[float]] = {}
        self._index_lock = asyncio.Lock()

    async def warm(self) -> None:
        await self._ensure_route_vectors(
            _NEW_ROUTES + _ACTIVE_SCHEDULING_ROUTES + _FALLBACK_ROUTES
        )

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        routes = (
            _ACTIVE_SCHEDULING_ROUTES
            if state.active_workflow == ActiveWorkflow.SCHEDULING
            else _NEW_ROUTES
        )
        return await self._choose(user_message, routes)

    async def route_non_scheduling(
        self,
        state: SessionState,
        user_message: str,
    ) -> RoutingDecision:
        relation = RouteRelation.INTERRUPT if state.active_workflow else RouteRelation.NEW
        routes = tuple(
            Route(route.key, route.domain, relation, route.description)
            for route in _FALLBACK_ROUTES
        )
        return await self._choose(user_message, routes)

    async def _choose(
        self,
        user_message: str,
        routes: tuple[Route, ...],
    ) -> RoutingDecision:
        await self._ensure_route_vectors(routes)
        query_vector = await self._embeddings.embed_query(
            user_message,
            EmbeddingTask.ROUTING,
        )
        scores = [
            cosine_similarity(query_vector, self._route_vectors[route.key])
            for route in routes
        ]
        best_index = max(range(len(routes)), key=scores.__getitem__)
        chosen = routes[best_index]
        return self._decision(chosen, scores[best_index], routes, scores)

    async def _ensure_route_vectors(self, routes: tuple[Route, ...]) -> None:
        missing = [route for route in routes if route.key not in self._route_vectors]
        if not missing:
            return
        async with self._index_lock:
            missing = [route for route in routes if route.key not in self._route_vectors]
            if not missing:
                return
            vectors = await self._embeddings.embed_documents(
                [route.description for route in missing]
            )
            if len(vectors) != len(missing):
                raise ValueError("Embedding service returned an unexpected route vector count")
            for route, vector in zip(missing, vectors, strict=True):
                self._route_vectors[route.key] = vector

    @staticmethod
    def _decision(
        route: Route,
        confidence: float,
        routes: tuple[Route, ...],
        scores: list[float],
    ) -> RoutingDecision:
        return RoutingDecision(
            domain=route.domain,
            relation=route.relation,
            route_key=route.key,
            confidence=max(0.0, min(1.0, confidence)),
            source="embedding",
            scores={
                item.key: score
                for item, score in zip(routes, scores, strict=True)
            },
        )
