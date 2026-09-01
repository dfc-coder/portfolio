from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Route(StrEnum):
    CONVERSATION = "conversation"
    PORTFOLIO = "portfolio"
    SCHEDULING = "scheduling"


class RouteRelation(StrEnum):
    NEW = "new"
    CONTINUE = "continue"
    INTERRUPT = "interrupt"


class RoutingDecision(BaseModel):
    domain: Route
    route_key: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str
    scores: dict[str, float] = Field(default_factory=dict)
