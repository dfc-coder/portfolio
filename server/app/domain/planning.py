from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentAction(StrEnum):
    ANSWER = "answer"
    ASK_FOR_DATES = "ask_for_dates"
    GET_AVAILABILITY = "get_availability"
    SELECT_SLOT = "select_slot"
    ASK_FOR_DETAILS = "ask_for_details"
    PREPARE_BOOKING = "prepare_booking"
    CANCEL_BOOKING = "cancel_booking"


class Plan(BaseModel):
    action: AgentAction
    start_date: date | None = None
    end_date: date | None = None
    slot_id: str | None = None
    visitor_name: str | None = None
    visitor_email: str | None = None
    subject: str | None = None


class ObservationType(StrEnum):
    SUCCESS = "success"
    AVAILABLE_SLOTS = "available_slots"
    MISSING_FIELDS = "missing_fields"
    INVALID_SLOT = "invalid_slot"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    TOOL_ERROR = "tool_error"


class Observation(BaseModel):
    type: ObservationType
    data: dict[str, Any] = Field(default_factory=dict)
    requires_next_step: bool = False


class VerificationResult(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)

    @classmethod
    def pass_(cls) -> "VerificationResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, *issues: str) -> "VerificationResult":
        return cls(ok=False, issues=list(issues))
