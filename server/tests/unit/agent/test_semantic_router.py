from __future__ import annotations

import math

import pytest

from app.agent.router import (
    SemanticRouter,
    _BUSINESS_UTTERANCES,
    _SCHEDULING_CONTINUE_UTTERANCES,
    _SCHEDULING_UTTERANCES,
)
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import RouteDomain, RouteRelation


class RoutingEmbeddings:
    def __init__(self) -> None:
        self.document_calls = 0
        self.query = ""
        self.query_vectors: dict[str, list[float]] = {
            "business": [1.0, 0.0, 0.0, 0.0],
            "scheduling": [0.0, 1.0, 0.0, 0.0],
            "continue": [0.0, 0.0, 1.0, 0.0],
            "general": [0.0, 0.0, 0.0, 1.0],
            "ambiguous": [math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0],
        }

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        vectors: list[list[float]] = []
        for text in texts:
            if text in _BUSINESS_UTTERANCES:
                vectors.append(self.query_vectors["business"])
            elif text in _SCHEDULING_UTTERANCES:
                vectors.append(self.query_vectors["scheduling"])
            elif text in _SCHEDULING_CONTINUE_UTTERANCES:
                vectors.append(self.query_vectors["continue"])
            else:
                raise AssertionError(f"Unexpected route utterance: {text}")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        self.query = text
        mapping = {
            "¿Cuánto cobra Diego por hora?": "business",
            "¿Qué podés hacer?": "business",
            "Antes, ¿Diego trabaja con AWS?": "business",
            "¿A qué hora podemos hablar?": "scheduling",
            "Quiero una reunión el martes": "scheduling",
            "Mi email es ana@example.com": "continue",
            "¿Qué hora es?": "general",
            "Esto podría ser trabajo o una reunión": "ambiguous",
        }
        return self.query_vectors[mapping[text]]

    async def health(self) -> bool:
        return True


def make_router(embeddings: RoutingEmbeddings) -> SemanticRouter:
    return SemanticRouter(
        embeddings,
        business_threshold=0.80,
        scheduling_threshold=0.80,
        continuation_threshold=0.80,
        min_margin=0.05,
    )


@pytest.mark.asyncio
async def test_open_set_router_selects_business() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)

    decision = await router.route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "semantic-router"


@pytest.mark.asyncio
async def test_open_set_router_selects_scheduling() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)

    decision = await router.route(SessionState("s2"), "¿A qué hora podemos hablar?")

    assert decision.domain == RouteDomain.SCHEDULING
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "semantic-router"


@pytest.mark.asyncio
async def test_unrelated_time_question_abstains_to_general() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)

    decision = await router.route(SessionState("time"), "¿Qué hora es?")

    assert decision.domain == RouteDomain.GENERAL
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "semantic-router:no-match"


@pytest.mark.asyncio
async def test_ambiguous_positive_routes_abstain_to_general() -> None:
    embeddings = RoutingEmbeddings()
    router = SemanticRouter(
        embeddings,
        business_threshold=0.60,
        scheduling_threshold=0.60,
        continuation_threshold=0.60,
        min_margin=0.05,
    )

    decision = await router.route(
        SessionState("ambiguous"),
        "Esto podría ser trabajo o una reunión",
    )

    assert decision.domain == RouteDomain.GENERAL
    assert decision.source == "semantic-router:ambiguous"


@pytest.mark.asyncio
async def test_new_turn_routing_uses_latest_visitor_text_only() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)
    state = SessionState("latest")
    state.turns = [
        ChatTurn(
            role="assistant",
            content="I can also help you find a time to talk with Diego.",
        )
    ]

    decision = await router.route(state, "¿Qué podés hacer?")

    assert decision.domain == RouteDomain.BUSINESS
    assert embeddings.query == "¿Qué podés hacer?"


@pytest.mark.asyncio
async def test_active_scheduling_continuation_uses_contextual_route() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)
    state = SessionState("continue")
    state.active_workflow = ActiveWorkflow.SCHEDULING

    decision = await router.route(state, "Mi email es ana@example.com")

    assert decision.domain == RouteDomain.SCHEDULING
    assert decision.relation == RouteRelation.CONTINUE
    assert decision.route_key == "scheduling_continue"


@pytest.mark.asyncio
async def test_active_scheduling_business_interrupt_preserves_memory() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)
    state = SessionState("interrupt")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"

    decision = await router.route(state, "Antes, ¿Diego trabaja con AWS?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.INTERRUPT
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_name == "Ana"


@pytest.mark.asyncio
async def test_active_scheduling_unrelated_question_is_general_interrupt() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)
    state = SessionState("general-interrupt")
    state.active_workflow = ActiveWorkflow.SCHEDULING

    decision = await router.route(state, "¿Qué hora es?")

    assert decision.domain == RouteDomain.GENERAL
    assert decision.relation == RouteRelation.INTERRUPT
    assert decision.source == "semantic-router:no-match"
    assert state.active_workflow == ActiveWorkflow.SCHEDULING


@pytest.mark.asyncio
async def test_non_scheduling_recheck_cannot_return_scheduling() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)

    decision = await router.route_non_scheduling(
        SessionState("fallback"),
        "Quiero una reunión el martes",
    )

    assert decision.domain == RouteDomain.GENERAL
    assert decision.source == "semantic-router:no-match"


@pytest.mark.asyncio
async def test_route_utterance_embeddings_are_warmed_once() -> None:
    embeddings = RoutingEmbeddings()
    router = make_router(embeddings)
    state = SessionState("cache")

    await router.warm()
    warmed_document_calls = embeddings.document_calls
    await router.route(state, "¿Cuánto cobra Diego por hora?")
    await router.route(state, "¿Qué hora es?")

    assert warmed_document_calls == 3
    assert embeddings.document_calls == warmed_document_calls
