from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from .routing import RouteDomain, RouteRelation


class DialogueAct(StrEnum):
    QUESTION = "question"
    REQUEST = "request"
    INFORM = "inform"
    SELECT = "select"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    NOT_APPLICABLE = "not_applicable"


class SchedulingCommand(BaseModel):
    """Semantic interpretation of one visitor turn inside the scheduling domain.

    The command describes meaning and extracted arguments only. It never names a
    tool or dictates a workflow transition.
    """

    act: DialogueAct
    start_date: date | None = None
    end_date: date | None = None
    slot_id: str | None = None
    visitor_name: str | None = None
    visitor_email: str | None = None
    subject: str | None = None


class SemanticDecision(BaseModel):
    domain: RouteDomain
    relation: RouteRelation
    act: DialogueAct
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str
