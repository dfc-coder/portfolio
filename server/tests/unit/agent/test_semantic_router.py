from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent.semantic_router import CascadingSemanticRouter, RoutingJudgeOutput
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain, RouteRelation
from app.ports.llm import GenerationConfig


class FixedReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.documents: list[str] = []

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        assert "VISITOR_MESSAGE" in query
        self.documents = documents
        return self.scores[: len(documents)]

    async def health(self) -> bool:
        return True


class JudgeLlm:
    def __init__(self, route_key: str) -> None:
        self.route_key = route_key
        self.calls = 0

    async def complete(self, messages: list[dict[str, Any]], config: GenerationConfig, response_schema: type[BaseModel] | None = None) -> str:
        del messages, config
        self.calls += 1
        assert response_schema is RoutingJudgeOutput
        return json.dumps({"route_key": self.route_key})

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        if False:
            yield ""

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_high_margin_reranker_routes_without_llm_judge() -> None:
    router = CascadingSemanticRouter(FixedReranker([0.92, 0.10, 0.05]), JudgeLlm("general_new"), GenerationConfig(temperature=0.05, max_tokens=48))
    decision = await router.route(SessionState("s1"), "¿Cuánto cobra Diego por hora?")
    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.NEW
    assert decision.source == "reranker"


@pytest.mark.asyncio
async def test_ambiguous_scores_escalate_to_llm_judge() -> None:
    llm = JudgeLlm("scheduling_new")
    router = CascadingSemanticRouter(FixedReranker([0.51, 0.50, 0.10]), llm, GenerationConfig(temperature=0.05, max_tokens=48))
    decision = await router.route(SessionState("s2"), "¿A qué hora podemos hablar?")
    assert decision.domain == RouteDomain.SCHEDULING
    assert decision.source == "llm_judge"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_active_scheduling_business_interrupt_preserves_belief() -> None:
    router = CascadingSemanticRouter(FixedReranker([0.95, 0.08, 0.04]), JudgeLlm("general_interrupt"), GenerationConfig(temperature=0.05, max_tokens=48))
    state = SessionState("s3")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_name = "Ana"

    decision = await router.route(state, "Antes, ¿Diego trabaja con AWS?")

    assert decision.domain == RouteDomain.BUSINESS
    assert decision.relation == RouteRelation.INTERRUPT
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_name == "Ana"
