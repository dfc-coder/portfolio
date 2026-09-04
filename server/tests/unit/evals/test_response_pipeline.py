from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.domain.conversation import SessionState
from app.portfolio.search import Fact, SearchResult
from tests.evals.responses.grader import ResponseCase
from tests.evals.run_response_eval import run_eval, run_prompt


class FakePortfolio:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str) -> SearchResult:
        self.queries.append(query)
        return SearchResult(
            facts=(Fact(text="Diego works with MuleSoft.", source="profile.skills"),)
        )


class FakeResponder:
    def __init__(self) -> None:
        self.calls: list[tuple[SessionState, tuple[Fact, ...]]] = []

    async def stream(
        self,
        state: SessionState,
        trace: Any = None,
        *,
        evidence: tuple[Fact, ...] = (),
    ) -> AsyncIterator[str]:
        del trace
        self.calls.append((state, evidence))
        yield "Respuesta de prueba"


class FakeGraderLlm:
    async def complete(self, messages, config, response_schema=None) -> str:
        del messages, config, response_schema
        return (
            '{"relevance":1.0,"groundedness":1.0,"completeness":1.0,'
            '"language_ok":true,"identity_ok":true,"action_safety_ok":true,'
            '"reason":"ok"}'
        )


def make_case(case_id: str, route: str, message: str) -> ResponseCase:
    return ResponseCase(
        case_id=case_id,
        message=message,
        route=route,
        language="es",
        critical=False,
        required_groups=(),
        forbidden=(),
        max_words=120,
    )


@pytest.mark.asyncio
async def test_run_prompt_retrieves_portfolio_evidence_before_generation() -> None:
    portfolio = FakePortfolio()
    responder = FakeResponder()
    case = make_case("portfolio-1", "portfolio", "¿Trabaja con MuleSoft?")

    result = await run_prompt(  # type: ignore[arg-type]
        case,
        responder=responder,
        portfolio=portfolio,
    )

    assert result.response == "Respuesta de prueba"
    assert result.prompt_id == "portfolio-agent-v1"
    assert portfolio.queries == [case.message]
    assert result.evidence[0].source == "profile.skills"
    assert responder.calls[0][0].turns[-1].content == case.message
    assert responder.calls[0][1] == result.evidence


@pytest.mark.asyncio
async def test_run_eval_returns_one_graded_record_per_case() -> None:
    portfolio = FakePortfolio()
    responder = FakeResponder()
    grader = FakeGraderLlm()
    cases = [
        make_case("conversation-1", "conversation", "Hola"),
        make_case("portfolio-1", "portfolio", "¿Trabaja con MuleSoft?"),
    ]

    records = await run_eval(  # type: ignore[arg-type]
        cases,
        responder=responder,
        portfolio=portfolio,
        grader_llm=grader,
    )

    assert [record["case_id"] for record in records] == [
        "conversation-1",
        "portfolio-1",
    ]
    assert all(record["response"] == "Respuesta de prueba" for record in records)
    assert all(record["hard_contract_pass"] for record in records)
    assert records[0]["prompt_id"] == "conversation-v1"
    assert records[1]["prompt_id"] == "portfolio-agent-v1"
    assert portfolio.queries == ["¿Trabaja con MuleSoft?"]
    assert records[0]["evidence_sources"] == []
    assert records[1]["evidence_sources"] == ["profile.skills"]
