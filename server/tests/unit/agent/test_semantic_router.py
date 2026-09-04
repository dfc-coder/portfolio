from __future__ import annotations

import math

import pytest

from app.agent.router import SemanticRouter
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import Intent, Route
from app.ports.embeddings import EmbeddingTask


class FixedEmbeddings:
    def __init__(self, scores: list[float], query_vector: list[float] | None = None) -> None:
        self.scores = scores
        self.query_vector = query_vector or [1.0, 0.0]
        self.documents: list[str] = []
        self.query = ""
        self.query_task: EmbeddingTask | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents = texts
        return [self._vector(self.scores[index] if index < len(self.scores) else self.scores[-1]) for index in range(len(texts))]

    async def embed_query(self, text: str, task: EmbeddingTask) -> list[float]:
        self.query = text
        self.query_task = task
        return self.query_vector

    async def health(self) -> bool:
        return True

    @staticmethod
    def _vector(score: float) -> list[float]:
        bounded = max(-1.0, min(1.0, score))
        return [bounded, math.sqrt(max(0.0, 1.0 - bounded * bounded))]


@pytest.mark.asyncio
async def test_embedding_router_selects_highest_portfolio_similarity() -> None:
    embeddings = FixedEmbeddings([0.92, 0.10, 0.05])
    decision = await SemanticRouter(embeddings).route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")
    assert decision.domain == Route.PORTFOLIO
    assert decision.source == "embedding"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_embedding_router_selects_scheduling_without_llm_judge() -> None:
    embeddings = FixedEmbeddings([0.50, 0.91, 0.10])
    decision = await SemanticRouter(embeddings).route(SessionState("s2"), "¿A qué hora podemos hablar?")
    assert decision.domain == Route.SCHEDULING
    assert decision.source == "embedding"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_new_turn_routing_uses_latest_visitor_text_only() -> None:
    embeddings = FixedEmbeddings([0.90, 0.05, 0.02])
    router = SemanticRouter(embeddings)
    state = SessionState("s-capabilities")
    state.turns = [ChatTurn(role="assistant", content="I can also help you find a time to talk with Diego.")]
    decision = await router.route(state, "¿Qué podés hacer?")
    assert decision.domain == Route.PORTFOLIO
    assert embeddings.query == "¿Qué podés hacer?"
    assert embeddings.query_task == EmbeddingTask.ROUTING
    assert "LAST_ASSISTANT" not in embeddings.query
    assert "CURRENT_FOCUS" not in embeddings.query


@pytest.mark.asyncio
async def test_active_scheduling_explicit_email_bypasses_embeddings() -> None:
    embeddings = FixedEmbeddings([0.05, 0.90, 0.02])
    router = SemanticRouter(embeddings)
    state = SessionState("s-workflow")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    decision = await router.route(state, "Mi email es ana@example.com")
    assert decision.domain == Route.SCHEDULING
    assert decision.intent == Intent.SCHEDULE_CONTINUE
    assert decision.source == "deterministic_scheduling"
    assert embeddings.query == ""
    assert embeddings.query_task is None


@pytest.mark.asyncio
async def test_active_scheduling_portfolio_interrupt_preserves_memory() -> None:
    embeddings = FixedEmbeddings([0.95, 0.08, 0.04])
    router = SemanticRouter(embeddings)
    state = SessionState("s3")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"
    decision = await router.route(state, "Antes, ¿Diego trabaja con AWS?")
    assert decision.domain == Route.PORTFOLIO
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
    assert len(first_documents) >= 3
    assert embeddings.documents == first_documents
    assert embeddings.query_task == EmbeddingTask.ROUTING
