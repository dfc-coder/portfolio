from __future__ import annotations

import pytest

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.scheduler import SchedulerReply
from app.domain.conversation import ActiveWorkflow, ChatTurn
from app.domain.profile import BusinessProfile
from app.domain.routing import Route, RouteRelation, RoutingDecision
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.portfolio.search import Fact, SearchResult
from app.scheduling.policy import SchedulingPolicy


class StaticRouter:
    def __init__(self, domain: Route) -> None:
        self.domain = domain

    async def route(self, state, user_message):  # type: ignore[no-untyped-def]
        del state, user_message
        return RoutingDecision(
            domain=self.domain,
            route_key=self.domain.value,
            confidence=1.0,
            source="test",
        )


class RecordingPortfolio:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def warm(self) -> None:
        return None

    async def search(self, query: str) -> SearchResult:
        self.queries.append(query)
        return SearchResult(
            facts=(
                Fact(
                    source="skills",
                    text='{"skills":{"cloud":["AWS"]}}',
                ),
            )
        )


class EvidenceLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return ""

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del config
        assert "RELEVANT_KNOWLEDGE:" in messages[0]["content"]
        assert "AWS" in messages[0]["content"]
        yield "Diego tiene experiencia con AWS."

    async def health(self) -> bool:
        return True


class UnusedScheduler:
    async def handle(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        raise AssertionError(f"scheduler should not run: {state}, {user_message}, {relation}")


class RecordingScheduler:
    def __init__(self) -> None:
        self.relation: RouteRelation | None = None

    async def handle(self, state, user_message, relation):  # type: ignore[no-untyped-def]
        del state, user_message
        self.relation = relation
        return SchedulerReply(text="continuemos con la reunión")


class UnusedResponder:
    async def stream(self, state, trace=None, *, evidence=()):  # type: ignore[no-untyped-def]
        raise AssertionError(f"responder should not run: {state}, {trace}, {evidence}")


@pytest.mark.asyncio
async def test_portfolio_route_searches_explicit_capability_and_preserves_scheduling(
    profile: BusinessProfile,
) -> None:
    sessions = MemorySessionStore()
    state = await sessions.get("session-portfolio")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.visitor_email = "ana@example.com"
    state.turns.extend(
        [
            ChatTurn(role="user", content="Contame sobre tu experiencia cloud"),
            ChatTurn(role="assistant", content="Texto previo que no debe entrar al retrieval"),
        ]
    )
    portfolio = RecordingPortfolio()
    responder = Responder(
        EvidenceLlm(),  # type: ignore[arg-type]
        profile,
        SchedulingPolicy(profile.scheduling),
        GenerationConfig(temperature=0.0, max_tokens=80),
        (),
    )
    agent = BusinessRepresentative(
        sessions,
        StaticRouter(Route.PORTFOLIO),  # type: ignore[arg-type]
        portfolio,  # type: ignore[arg-type]
        UnusedScheduler(),  # type: ignore[arg-type]
        responder,
    )

    answer = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-portfolio",
                "¿Y AWS?",
            )
        ]
    )
    state = await sessions.get("session-portfolio")

    assert "AWS" in answer
    assert portfolio.queries == ["Contame sobre tu experiencia cloud\n¿Y AWS?"]
    assert "Texto previo" not in portfolio.queries[0]
    assert state.current_focus == Route.PORTFOLIO
    assert state.active_workflow == ActiveWorkflow.SCHEDULING
    assert state.scheduling.visitor_email == "ana@example.com"


@pytest.mark.asyncio
async def test_representative_derives_scheduling_relation_outside_router() -> None:
    sessions = MemorySessionStore()
    state = await sessions.get("session-scheduling")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    scheduler = RecordingScheduler()
    agent = BusinessRepresentative(
        sessions,
        StaticRouter(Route.SCHEDULING),  # type: ignore[arg-type]
        RecordingPortfolio(),  # type: ignore[arg-type]
        scheduler,  # type: ignore[arg-type]
        UnusedResponder(),  # type: ignore[arg-type]
    )

    answer = "".join(
        [
            chunk
            async for chunk in agent.respond(
                "session-scheduling",
                "mi email es ana@example.com",
            )
        ]
    )

    assert answer == "continuemos con la reunión"
    assert scheduler.relation == RouteRelation.CONTINUE
