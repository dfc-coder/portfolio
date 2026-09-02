from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.routing import Intent, Route, RoutingDecision


def test_capability_query_is_distinct_from_scheduling_request() -> None:
    assert Intent.CAPABILITY_QUERY != Intent.SCHEDULE_REQUEST


def test_abstained_decision_has_no_business_route() -> None:
    decision = RoutingDecision(
        domain=None,
        intent=None,
        accepted=False,
        route_key="abstain",
        confidence=0.41,
        margin=0.02,
        source="abstain",
        scores={
            Intent.CAPABILITY_QUERY.value: 0.41,
            Intent.CONVERSATION.value: 0.39,
        },
    )

    assert decision.accepted is False
    assert decision.domain is None
    assert decision.intent is None


def test_accepted_decision_requires_business_route() -> None:
    with pytest.raises(ValidationError, match="requires a domain"):
        RoutingDecision(
            domain=None,
            intent=Intent.CAPABILITY_QUERY,
            accepted=True,
            route_key="capability_query",
            confidence=0.91,
            margin=0.41,
            source="intent_classifier",
        )


def test_abstained_decision_rejects_business_route() -> None:
    with pytest.raises(ValidationError, match="cannot have a domain"):
        RoutingDecision(
            domain=Route.PORTFOLIO,
            accepted=False,
            route_key="abstain",
            confidence=0.51,
            margin=0.01,
            source="abstain",
        )
