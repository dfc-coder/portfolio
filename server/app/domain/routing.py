from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Route(StrEnum):
    CONVERSATION = "conversation"
    PORTFOLIO = "portfolio"
    SCHEDULING = "scheduling"


class Intent(StrEnum):
    PORTFOLIO_QUERY = "portfolio_query"
    CAPABILITY_QUERY = "capability_query"
    SCHEDULE_REQUEST = "schedule_request"
    SCHEDULE_AVAILABILITY = "schedule_availability"
    SCHEDULE_CONTINUE = "schedule_continue"
    CONVERSATION = "conversation"


class RouteRelation(StrEnum):
    NEW = "new"
    CONTINUE = "continue"
    INTERRUPT = "interrupt"


class RoutingDecision(BaseModel):
    domain: Route | None
    intent: Intent | None = None
    accepted: bool = True
    route_key: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    margin: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str
    scores: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_acceptance(self) -> "RoutingDecision":
        if self.accepted and self.domain is None:
            raise ValueError("accepted routing decision requires a domain")
        if not self.accepted and self.domain is not None:
            raise ValueError("abstained routing decision cannot have a domain")
        return self
