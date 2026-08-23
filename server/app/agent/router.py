from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.ports.llm import GenerationConfig, LlmPort
from app.ports.reranker import RerankerPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Route:
    key: str
    domain: RouteDomain
    relation: RouteRelation
    description: str


class RouteChoice(BaseModel):
    route_key: str


_NEW_ROUTES = (
    Route(
        "business",
        RouteDomain.BUSINESS,
        RouteRelation.NEW,
        (
            "Questions about Diego's professional work, projects, technologies, services, "
            "rates, clients, credentials, capabilities, or what this representative can do. "
            "Capability questions are informational and do not start a meeting workflow."
        ),
    ),
    Route(
        "scheduling",
        RouteDomain.SCHEDULING,
        RouteRelation.NEW,
        (
            "An actual request to arrange, reschedule, cancel, select a time for, or check "
            "real availability for a meeting with Diego. Do not choose this route when the "
            "visitor only asks whether scheduling is a supported capability."
        ),
    ),
    Route(
        "general",
        RouteDomain.GENERAL,
        RouteRelation.NEW,
        "General conversation unrelated to Diego's professional work or an actual meeting task.",
    ),
)

_ACTIVE_SCHEDULING_ROUTES = (
    Route(
        "business_interrupt",
        RouteDomain.BUSINESS,
        RouteRelation.INTERRUPT,
        (
            "A professional question about Diego's work, projects, technologies, experience, "
            "skills, services, credentials or capabilities that interrupts the active meeting task. "
            "Preserve the meeting data and answer the professional question without advancing scheduling."
        ),
    ),
    Route(
        "scheduling_continue",
        RouteDomain.SCHEDULING,
        RouteRelation.CONTINUE,
        (
            "A continuation of the active meeting task: a date or date range, meeting details, "
            "slot selection, confirmation, availability request, change, rejection or cancellation."
        ),
    ),
    Route(
        "general_interrupt",
        RouteDomain.GENERAL,
        RouteRelation.INTERRUPT,
        "General conversation that interrupts the active meeting task. Preserve the meeting data.",
    ),
)

# High-precision boundary for clearly professional questions. These should never become
# scheduling merely because the reranker is uncertain or a meeting workflow is active.
_BUSINESS_QUESTION_RE = re.compile(
    r"\b(?:"
    r"experiencia|experience|trabaja|work(?:ed|s|ing)?|proyecto(?:s)?|projects?|"
    r"tecnolog(?:ia|ía|ias|ías)|technolog(?:y|ies)|skills?|habilidades?|"
    r"certificaciones?|certifications?|stack|lenguajes?|languages?|"
    r"frameworks?|aws|python|rust|golang|\bgo\b|typescript|javascript|"
    r"langgraph|langchain|rag|mcp|fastapi|sql|mulesoft"
    r")\b",
    re.IGNORECASE,
)


class SemanticRouter:
    """Three-way semantic routing: explicit boundaries, reranker, then tiny LLM on ambiguity."""

    def __init__(
        self,
        reranker: RerankerPort,
        llm: LlmPort,
        judge_config: GenerationConfig,
        *,
        min_score: float = 0.10,
        min_margin: float = 0.08,
    ) -> None:
        self._reranker = reranker
        self._llm = llm
        self._judge_config = judge_config
        self._min_score = min_score
        self._min_margin = min_margin

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        routes = (
            _ACTIVE_SCHEDULING_ROUTES
            if state.active_workflow == ActiveWorkflow.SCHEDULING
            else _NEW_ROUTES
        )
        explicit_business = self._explicit_business_route(user_message, routes)
        if explicit_business is not None:
            return self._decision(explicit_business, 1.0, "explicit_business_boundary", routes, [])
        return await self._choose(state, user_message, routes)

    async def route_non_scheduling(
        self,
        state: SessionState,
        user_message: str,
    ) -> RoutingDecision:
        relation = RouteRelation.INTERRUPT if state.active_workflow else RouteRelation.NEW
        routes = (
            Route("business_fallback", RouteDomain.BUSINESS, relation, _NEW_ROUTES[0].description),
            Route("general_fallback", RouteDomain.GENERAL, relation, _NEW_ROUTES[2].description),
        )
        explicit_business = self._explicit_business_route(user_message, routes)
        if explicit_business is not None:
            return self._decision(explicit_business, 1.0, "explicit_business_boundary", routes, [])
        return await self._choose(state, user_message, routes)

    async def _choose(
        self,
        state: SessionState,
        user_message: str,
        routes: tuple[Route, ...],
    ) -> RoutingDecision:
        query = self._query(state, user_message)
        scores: list[float] = []
        try:
            scores = await self._reranker.rerank(
                query,
                [route.description for route in routes],
            )
            ranked = sorted(
                zip(routes, scores, strict=True),
                key=lambda item: item[1],
                reverse=True,
            )
            top, top_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            if top_score >= self._min_score and top_score - second_score >= self._min_margin:
                return self._decision(top, top_score, "reranker", routes, scores)
        except Exception as exc:
            logger.warning("semantic reranker unavailable: %s", exc)

        return await self._judge(query, routes, scores)

    async def _judge(
        self,
        query: str,
        routes: tuple[Route, ...],
        scores: list[float],
    ) -> RoutingDecision:
        allowed = {route.key: route.description for route in routes}
        messages = [
            {
                "role": "system",
                "content": "Choose exactly one route_key from ROUTES. Do not answer the visitor.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"CONTEXT": query, "ROUTES": allowed},
                    ensure_ascii=False,
                ),
            },
        ]
        chosen: Route | None = None
        source = "llm_judge"
        try:
            raw = await self._llm.complete(
                messages,
                self._judge_config,
                response_schema=RouteChoice,
            )
            parsed = RouteChoice.model_validate_json(raw)
            chosen = next((route for route in routes if route.key == parsed.route_key), None)
        except Exception as exc:
            logger.warning("routing judge failed: %s", exc)

        if chosen is None:
            if scores:
                chosen = routes[max(range(len(scores)), key=scores.__getitem__)]
                source = "reranker_fallback"
            else:
                chosen = next(
                    (route for route in routes if route.domain == RouteDomain.GENERAL),
                    routes[0],
                )
                source = "safe_fallback"

        score = scores[routes.index(chosen)] if scores and chosen in routes else 0.5
        return self._decision(chosen, score, source, routes, scores)

    @staticmethod
    def _explicit_business_route(user_message: str, routes: tuple[Route, ...]) -> Route | None:
        if not _BUSINESS_QUESTION_RE.search(user_message):
            return None
        return next((route for route in routes if route.domain == RouteDomain.BUSINESS), None)

    @staticmethod
    def _query(state: SessionState, user_message: str) -> str:
        # Route the meaning of the latest visitor turn only. The active workflow is already
        # represented by the candidate route set; injecting workflow/state text into the
        # reranker query biases unrelated professional questions toward scheduling_continue.
        del state
        return f"VISITOR: {user_message.strip()}"

    @staticmethod
    def _decision(
        route: Route,
        confidence: float,
        source: str,
        routes: tuple[Route, ...],
        scores: list[float],
    ) -> RoutingDecision:
        score_map = (
            {item.key: score for item, score in zip(routes, scores, strict=True)}
            if scores
            else {}
        )
        return RoutingDecision(
            domain=route.domain,
            relation=route.relation,
            route_key=route.key,
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
            scores=score_map,
        )
