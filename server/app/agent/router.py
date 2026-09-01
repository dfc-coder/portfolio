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
            "A question about Diego as a professional: his background, experience, projects, "
            "technologies, skills, services, education, credentials, languages, rates, clients or "
            "capabilities. This is not a request to arrange contact or a meeting."
        ),
    ),
    Route(
        "scheduling",
        RouteDomain.SCHEDULING,
        RouteRelation.NEW,
        (
            "A request to contact, call, talk with or meet Diego on a day, date or time; check his "
            "calendar availability; book, reschedule or cancel a meeting."
        ),
    ),
    Route(
        "general",
        RouteDomain.GENERAL,
        RouteRelation.NEW,
        (
            "Conversation unrelated to Diego's professional profile and unrelated to arranging "
            "contact with him, such as greetings, thanks, jokes, weather, general knowledge or "
            "casual chat."
        ),
    ),
)

_ACTIVE_SCHEDULING_ROUTES = (
    Route(
        "business_interrupt",
        RouteDomain.BUSINESS,
        RouteRelation.INTERRUPT,
        (
            "While scheduling is active, the visitor switches to a question about Diego as a "
            "professional: experience, projects, technologies, skills, services, education, "
            "credentials, languages, rates, clients or capabilities. This is not meeting logistics."
        ),
    ),
    Route(
        "scheduling_continue",
        RouteDomain.SCHEDULING,
        RouteRelation.CONTINUE,
        (
            "While scheduling is active, the visitor continues the meeting logistics by giving or "
            "changing a day, date or time; choosing a slot; providing a name, email or subject; "
            "confirming, rescheduling or cancelling."
        ),
    ),
    Route(
        "general_interrupt",
        RouteDomain.GENERAL,
        RouteRelation.INTERRUPT,
        (
            "While scheduling is active, the visitor switches to casual or unrelated conversation, "
            "such as a greeting, thanks, joke, weather, general knowledge or other non-professional, "
            "non-scheduling chat."
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
