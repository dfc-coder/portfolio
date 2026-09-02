from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import Intent, Route, RoutingDecision
from app.infrastructure.embeddings.similarity import cosine_similarity
from app.infrastructure.intent_classifier import IntentClassifier, IntentPrediction
from app.ports.embeddings import EmbeddingPort, EmbeddingTask
from app.scheduling.turn_parser import SchedulingTurnParser


@dataclass(frozen=True)
class _Candidate:
    key: str
    domain: Route
    description: str


_NEW_ROUTES = (
    _Candidate(
        "portfolio_professional",
        Route.PORTFOLIO,
        (
            "A question about Diego as a professional: his background, experience, "
            "technologies, integrations, architecture, skills, credentials, languages, "
            "clients or professional technical work."
        ),
    ),
    _Candidate(
        "scheduling_action",
        Route.SCHEDULING,
        (
            "A request or instruction to actually arrange, book, reschedule or cancel "
            "a meeting or call with Diego."
        ),
    ),
    _Candidate(
        "conversation_general",
        Route.CONVERSATION,
        (
            "General conversation unrelated to Diego's professional profile and unrelated "
            "to arranging a meeting, such as greetings, thanks, jokes, weather, current "
            "time or general knowledge."
        ),
    ),
    _Candidate(
        "portfolio_projects",
        Route.PORTFOLIO,
        (
            "A question about one of Diego's projects or implementations: project details, "
            "architecture, stack, programming language, MCP servers, APIs, integrations "
            "or implementation decisions."
        ),
    ),
    _Candidate(
        "portfolio_capabilities",
        Route.PORTFOLIO,
        (
            "A question asking what Diego or this representative can do, what tools or "
            "capabilities it supports, or whether it is able to perform an action. "
            "This asks about a capability; it does not request that action now."
        ),
    ),
    _Candidate(
        "portfolio_technical_approach",
        Route.PORTFOLIO,
        (
            "A question about Diego's technical approach or expertise, including APIs, "
            "integrations, local models, LLM systems, architecture and security."
        ),
    ),
    _Candidate(
        "scheduling_availability",
        Route.SCHEDULING,
        (
            "A request to check actual calendar availability or available meeting times "
            "or slots for a particular day, date or date range."
        ),
    ),
    _Candidate(
        "scheduling_contact",
        Route.SCHEDULING,
        (
            "A request to actually speak, talk, call or meet with Diego, especially on "
            "a concrete day, date or time."
        ),
    ),
    _Candidate(
        "conversation_unrelated",
        Route.CONVERSATION,
        (
            "A question unrelated to Diego and unrelated to meeting logistics, such as "
            "the current time, weather, sports, definitions, general knowledge or casual chat."
        ),
    ),
)

_ACTIVE_SCHEDULING_ROUTES = (
    _Candidate(
        "portfolio_during_scheduling",
        Route.PORTFOLIO,
        (
            "While scheduling is active, the visitor switches to a professional question "
            "about Diego's experience, technologies, skills, architecture or work."
        ),
    ),
    _Candidate(
        "scheduling_continue",
        Route.SCHEDULING,
        (
            "While scheduling is active, the visitor continues the meeting logistics, "
            "including choosing or changing meeting details, confirmation, rescheduling "
            "or cancellation."
        ),
    ),
    _Candidate(
        "conversation_during_scheduling",
        Route.CONVERSATION,
        (
            "While scheduling is active, the visitor switches to unrelated casual "
            "conversation such as greetings, thanks, jokes or small talk."
        ),
    ),
    _Candidate(
        "portfolio_capabilities_during_scheduling",
        Route.PORTFOLIO,
        (
            "While scheduling is active, the visitor asks what Diego or this representative "
            "can do, what tools it supports or what capabilities are available. "
            "This is not meeting logistics."
        ),
    ),
    _Candidate(
        "portfolio_projects_during_scheduling",
        Route.PORTFOLIO,
        (
            "While scheduling is active, the visitor asks about Diego's projects, "
            "technologies, APIs, integrations, architecture or technical expertise."
        ),
    ),
    _Candidate(
        "conversation_general_during_scheduling",
        Route.CONVERSATION,
        (
            "While scheduling is active, the visitor asks an unrelated general question "
            "such as the current time, weather, general knowledge or another casual topic."
        ),
    ),
)


_INTENT_ROUTES = {
    Intent.PORTFOLIO_QUERY: Route.PORTFOLIO,
    Intent.CAPABILITY_QUERY: Route.PORTFOLIO,
    Intent.SCHEDULE_REQUEST: Route.SCHEDULING,
    Intent.SCHEDULE_AVAILABILITY: Route.SCHEDULING,
    Intent.SCHEDULE_CONTINUE: Route.SCHEDULING,
    Intent.CONVERSATION: Route.CONVERSATION,
}


def route_for_intent(intent: Intent) -> Route:
    return _INTENT_ROUTES[intent]


def _has_explicit_scheduling_fields(user_message: str) -> bool:
    """Reuse the scheduling parser's deterministic extractors; do not add routing regexes."""
    text = user_message.strip()
    start_date, _ = SchedulingTurnParser._extract_dates(text, date.today())
    return any(
        value is not None
        for value in (
            SchedulingTurnParser._extract_email(text),
            SchedulingTurnParser._extract_slot(text),
            start_date,
            SchedulingTurnParser._extract_name(text),
            SchedulingTurnParser._extract_subject(text),
        )
    )


class SemanticRouter:
    """Embedding baseline. It never dispatches Python capabilities."""

    def __init__(self, embeddings: EmbeddingPort) -> None:
        self._embeddings = embeddings
        self._route_vectors: dict[str, list[float]] = {}
        self._index_lock = asyncio.Lock()

    async def warm(self) -> None:
        await self._ensure_route_vectors(_NEW_ROUTES + _ACTIVE_SCHEDULING_ROUTES)

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        if (
            state.active_workflow == ActiveWorkflow.SCHEDULING
            and _has_explicit_scheduling_fields(user_message)
        ):
            return RoutingDecision(
                domain=Route.SCHEDULING,
                intent=Intent.SCHEDULE_CONTINUE,
                route_key="scheduling_explicit",
                confidence=1.0,
                margin=1.0,
                source="deterministic_scheduling",
                scores={Intent.SCHEDULE_CONTINUE.value: 1.0},
            )

        routes = (
            _ACTIVE_SCHEDULING_ROUTES
            if state.active_workflow == ActiveWorkflow.SCHEDULING
            else _NEW_ROUTES
        )
        return await self._choose(user_message, routes)

    async def _choose(
        self,
        user_message: str,
        routes: tuple[_Candidate, ...],
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

    async def _ensure_route_vectors(self, routes: tuple[_Candidate, ...]) -> None:
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
        route: _Candidate,
        confidence: float,
        routes: tuple[_Candidate, ...],
        scores: list[float],
    ) -> RoutingDecision:
        ranked = sorted(scores, reverse=True)
        margin = ranked[0] - ranked[1] if len(ranked) > 1 else 1.0
        return RoutingDecision(
            domain=route.domain,
            route_key=route.key,
            confidence=max(0.0, min(1.0, confidence)),
            margin=max(0.0, min(1.0, margin)),
            source="embedding",
            scores={
                item.key: score
                for item, score in zip(routes, scores, strict=True)
            },
        )


class IntentRouter:
    """Supervised intent router evaluated before it is promoted to the runtime."""

    def __init__(
        self,
        embeddings: EmbeddingPort,
        classifier: IntentClassifier,
    ) -> None:
        self._embeddings = embeddings
        self._classifier = classifier

    async def warm(self) -> None:
        return None

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        if (
            state.active_workflow == ActiveWorkflow.SCHEDULING
            and _has_explicit_scheduling_fields(user_message)
        ):
            return RoutingDecision(
                domain=Route.SCHEDULING,
                intent=Intent.SCHEDULE_CONTINUE,
                route_key="scheduling_explicit",
                confidence=1.0,
                margin=1.0,
                source="deterministic_scheduling",
                scores={Intent.SCHEDULE_CONTINUE.value: 1.0},
            )

        embedding = await self._embeddings.embed_query(
            user_message,
            EmbeddingTask.ROUTING,
        )
        prediction = self._classifier.predict(embedding)
        return self._decision(prediction)

    def _decision(self, prediction: IntentPrediction) -> RoutingDecision:
        accepted = self._classifier.accepts(prediction)
        return RoutingDecision(
            domain=route_for_intent(prediction.intent) if accepted else None,
            intent=prediction.intent if accepted else None,
            accepted=accepted,
            route_key=prediction.intent.value if accepted else "abstain",
            confidence=prediction.confidence,
            margin=prediction.margin,
            source="intent_classifier" if accepted else "abstain",
            scores=prediction.scores,
        )
