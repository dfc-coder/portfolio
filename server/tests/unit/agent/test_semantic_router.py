from __future__ import annotations

import math

import pytest

from app.agent.router import SemanticRouter
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import RouteDomain, RouteRelation
from app.ports.embeddings import EmbeddingTask


class FixedEmbeddings:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.documents: list[str] = []
        self.query = ""
        self.query_task: EmbeddingTask | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents = texts
        return [self._vector(score) for score in self.scores[: len(texts)]]

    async def embed_query(self, text: str, task: EmbeddingTask) -> list[float]:
        self.query = text
        self.query_task = task
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True

    @staticmethod
    def _vector(score: float) -> list[float]:
        bounded = max(-1.0, min(1.0, score))
        return [bounded, math.sqrt(max(0.0, 1.0 - bounded * bounded))]


@pytest.mark.asyncio
async def test_embedding_router_selects_highest_business_similarity() -> None:
    embeddings = FixedEmbeddings([0.92, 0.10, 0.05])
    router = SemanticRouter(embeddings)

    decision = await router.route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "embedding"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_embedding_router_selects_scheduling_without_llm_judge() -> None:
    embeddings = FixedEmbeddings([0.50, 0.91, 0.10])
    router = SemanticRouter(embeddings)

    decision = await router.route(SessionState("s2"), "¿A qué hora podemos hablar?")

    assert decision.domain == RouteDomain.SCHEDULING
    assert decision.source == "embedding"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_new_turn_routing_uses_latest_visitor_text_only() -> None:
    embeddings = FixedEmbeddings([0.90, 0.05, 0.02])
    router = SemanticRouter(embeddings)
    state = SessionState("s-capabilities")
    state.turns = [
        ChatTurn(
            role="assistant",
            content="I can also help you find a time to talk with Diego.",
        )
    ]

    decision = await router.route(state, "¿Qué podés hacer?")

    assert decision.domain == RouteDomain.BUSINESS
    assert embeddings.query == "¿Qué podés hacer?"
    assert embeddings.query_task == EmbeddingTask.ROUTING
    assert "LAST_ASSISTANT" not in embeddings.query
    assert "CURRENT_FOCUS" not in embeddings.query


@pytest.mark.asyncio
async def test_active_scheduling_routes_latest_turn_without_workflow_text_in_query() -> None:
    embeddings = FixedEmbeddings([0.05, 0.90, 0.02])
    router = SemanticRouter(embeddings)
    state = SessionState("s-workflow")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"
    state.turns = [
        ChatTurn(
            role="assistant",
            content="Tell me which meeting slot you prefer.",
        )
    ]

    decision = await router.route(state, "Mi email es ana@example.com")

    assert decision.domain == RouteDomain.SCHEDULING
    assert embeddings.query == "Mi email es ana@example.com"
    assert embeddings.query_task == EmbeddingTask.ROUTING
    assert "ACTIVE_WORKFLOW" not in embeddings.query
    assert "SCHEDULING_FACTS" not in embeddings.query
    assert "visitor_name" not in embeddings.query
    assert "Tell me which meeting slot" not in embeddings.query


@pytest.mark.asyncio
async def test_active_scheduling_business_interrupt_preserves_memory() -> None:
    embeddings = FixedEmbeddings([0.95, 0.08, 0.04])
    router = SemanticRouter(embeddings)
    state = SessionState("s3")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"

    decision = await router.route(state, "Antes, ¿Diego trabaja con AWS?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.INTERRUPT
    assert embeddings.query_task == EmbeddingTask.ROUTING
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_name == "Ana"


@pytest.mark.asyncio
async def test_route_document_embeddings_are_cached() -> None:
    embeddings = FixedEmbeddings([0.95, 0.08, 0.04])
    router = SemanticRouter(embeddings)
    state = SessionState("s-cache")

    await router.route(state, "Diego tiene experiencia con Rust?")
    first_documents = list(embeddings.documents)
    await router.route(state, "¿Qué proyectos tiene?")

    assert len(first_documents) == 3
    assert len(embeddings.documents) == 3
    assert embeddings.query_task == EmbeddingTask.ROUTING
