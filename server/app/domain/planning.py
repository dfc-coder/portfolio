from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
