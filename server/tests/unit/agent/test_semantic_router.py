from __future__ import annotations

import math

import pytest

from app.agent.router import IntentRouter, SemanticRouter, route_for_intent
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import Intent, Route
from app.infrastructure.intent_classifier import IntentClassifier, IntentModel
from app.ports.embeddings import EmbeddingTask


class FixedEmbeddings:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.documents: list[str] = []
        self.query = ""
        self.query_task: EmbeddingTask | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents = texts
        return [
            self._vector(
                self.scores[index]
                if index < len(self.scores)
                else self.scores[-1]
            )
            for index in range(len(texts))
        ]

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


def classifier(
    *,
    min_confidence: float = 0.0,
    min_margin: float = 0.0,
) -> IntentClassifier:
    model = IntentModel(
        version=1,
        embedding_model="test",
        embedding_dimension=2,
        intents=(
            Intent.CAPABILITY_QUERY,
            Intent.SCHEDULE_REQUEST,
            Intent.CONVERSATION,
        ),
        coefficients=(
            (3.0, 0.0),
            (0.0, 2.0),
            (-1.0, 0.0),
        ),
        intercepts=(0.0, 0.0, 0.0),
        min_confidence=min_confidence,
        min_margin=min_margin,
        training_dataset_hash="test",
        seed=42,
    )
    return IntentClassifier(model)


@pytest.mark.parametrize(
    ("intent", "route"),
    [
        (Intent.PORTFOLIO_QUERY, Route.PORTFOLIO),
        (Intent.CAPABILITY_QUERY, Route.PORTFOLIO),
        (Intent.SCHEDULE_REQUEST, Route.SCHEDULING),
        (Intent.SCHEDULE_AVAILABILITY, Route.SCHEDULING),
        (Intent.SCHEDULE_CONTINUE, Route.SCHEDULING),
        (Intent.CONVERSATION, Route.CONVERSATION),
    ],
)
def test_intent_maps_to_business_route(intent: Intent, route: Route) -> None:
    assert route_for_intent(intent) == route


@pytest.mark.asyncio
async def test_embedding_router_selects_highest_portfolio_similarity() -> None:
    embeddings = FixedEmbeddings([0.92, 0.10, 0.05])
    router = SemanticRouter(embeddings)

    decision = await router.route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")

    assert decision.domain == Route.PORTFOLIO
    assert decision.source == "embedding"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_embedding_router_selects_scheduling_without_llm_judge() -> None:
    embeddings = FixedEmbeddings([0.50, 0.91, 0.10])
    router = SemanticRouter(embeddings)

    decision = await router.route(SessionState("s2"), "¿A qué hora podemos hablar?")

    assert decision.domain == Route.SCHEDULING
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


@pytest.mark.asyncio
async def test_intent_router_routes_confident_prediction() -> None:
    embeddings = FixedEmbeddings([0.1])
    router = IntentRouter(embeddings, classifier())

    decision = await router.route(SessionState("intent-1"), "¿Qué capacidades tenés?")

    assert decision.accepted is True
    assert decision.intent == Intent.CAPABILITY_QUERY
    assert decision.domain == Route.PORTFOLIO
    assert decision.source == "intent_classifier"
    assert embeddings.query_task == EmbeddingTask.ROUTING


@pytest.mark.asyncio
async def test_intent_router_abstains_when_thresholds_are_not_met() -> None:
    embeddings = FixedEmbeddings([0.1])
    router = IntentRouter(
        embeddings,
        classifier(min_confidence=0.99, min_margin=0.99),
    )

    decision = await router.route(SessionState("intent-2"), "mensaje ambiguo")

    assert decision.accepted is False
    assert decision.intent is None
    assert decision.domain is None
    assert decision.source == "abstain"


@pytest.mark.asyncio
async def test_intent_router_uses_structured_scheduling_before_classifier() -> None:
    embeddings = FixedEmbeddings([0.1])
    router = IntentRouter(embeddings, classifier())
    state = SessionState("intent-3")
    state.active_workflow = ActiveWorkflow.SCHEDULING

    decision = await router.route(state, "El segundo")

    assert decision.domain == Route.SCHEDULING
    assert decision.intent == Intent.SCHEDULE_CONTINUE
    assert decision.source == "deterministic_scheduling"
    assert embeddings.query == ""
