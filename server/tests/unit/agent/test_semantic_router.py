from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent.router import RouteChoice, SemanticRouter
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import RouteDomain, RouteRelation
from app.ports.llm import GenerationConfig


class FixedReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.documents: list[str] = []
        self.query = ""

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        assert "VISITOR:" in query
        self.query = query
        self.documents = documents
        return self.scores[: len(documents)]

    async def health(self) -> bool:
        return True


class JudgeLlm:
    def __init__(self, route_key: str) -> None:
        self.route_key = route_key
        self.calls = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        del messages, config
        self.calls += 1
        assert response_schema is RouteChoice
        return json.dumps({"route_key": self.route_key})

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        if False:
            yield ""

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_high_margin_reranker_routes_without_llm_judge() -> None:
    router = SemanticRouter(
        FixedReranker([0.92, 0.10, 0.05]),
        JudgeLlm("general"),
        GenerationConfig(temperature=0.05, max_tokens=48),
    )
    decision = await router.route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")
    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "reranker"


@pytest.mark.asyncio
async def test_ambiguous_scores_escalate_to_llm_judge() -> None:
    llm = JudgeLlm("scheduling")
    router = SemanticRouter(
        FixedReranker([0.51, 0.50, 0.10]),
        llm,
        GenerationConfig(temperature=0.05, max_tokens=48),
    )
    decision = await router.route(SessionState("s2"), "¿A qué hora podemos hablar?")
    assert decision.domain == RouteDomain.SCHEDULING
    assert decision.source == "llm_judge"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_new_turn_routing_does_not_include_previous_assistant_text() -> None:
    reranker = FixedReranker([0.90, 0.05, 0.02])
    router = SemanticRouter(
        reranker,
        JudgeLlm("general"),
        GenerationConfig(temperature=0.05, max_tokens=48),
    )
    state = SessionState("s-capabilities")
    state.turns = [
        ChatTurn(
            role="assistant",
            content="I can also help you find a time to talk with Diego.",
        )
    ]

    decision = await router.route(state, "¿Qué podés hacer?")

    assert decision.domain == RouteDomain.BUSINESS
    assert reranker.query == "VISITOR: ¿Qué podés hacer?"
    assert "LAST_ASSISTANT" not in reranker.query
    assert "CURRENT_FOCUS" not in reranker.query


@pytest.mark.asyncio
async def test_active_scheduling_routes_latest_turn_without_workflow_state_in_query() -> None:
    reranker = FixedReranker([0.05, 0.90, 0.02])
    router = SemanticRouter(
        reranker,
        JudgeLlm("general_interrupt"),
        GenerationConfig(temperature=0.05, max_tokens=48),
    )
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
    assert reranker.query == "VISITOR: Mi email es ana@example.com"
    assert "ACTIVE_WORKFLOW" not in reranker.query
    assert "SCHEDULING_FACTS" not in reranker.query
    assert "visitor_name" not in reranker.query
    assert "Tell me which meeting slot" not in reranker.query


@pytest.mark.asyncio
async def test_active_scheduling_business_interrupt_preserves_memory() -> None:
    router = SemanticRouter(
        FixedReranker([0.95, 0.08, 0.04]),
        JudgeLlm("general_interrupt"),
        GenerationConfig(temperature=0.05, max_tokens=48),
    )
    state = SessionState("s3")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"

    decision = await router.route(state, "Antes, ¿Diego trabaja con AWS?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.INTERRUPT
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_name == "Ana"


@pytest.mark.asyncio
async def test_active_scheduling_rust_experience_question_bypasses_bad_reranker_score() -> None:
    reranker = FixedReranker([0.01, 0.99, 0.00])
    router = SemanticRouter(
        reranker,
        JudgeLlm("scheduling_continue"),
        GenerationConfig(temperature=0.0, max_tokens=32),
    )
    state = SessionState("s-rust")
    state.active_workflow = ActiveWorkflow.SCHEDULING

    decision = await router.route(state, "Diego tiene experiencia con rust?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.INTERRUPT
    assert decision.source == "explicit_business_boundary"
    assert reranker.query == ""
