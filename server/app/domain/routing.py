from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RouteDomain(StrEnum):
    BUSINESS = "business"
    SCHEDULING = "scheduling"
    GENERAL = "general"


class RouteRelation(StrEnum):
    NEW = "new"
    CONTINUE = "continue"
    INTERRUPT = "interrupt"


class RoutingDecision(BaseModel):
    domain: RouteDomain
    relation: RouteRelation
    route_key: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str
    scores: dict[str, float] = Field(default_factory=dict)
