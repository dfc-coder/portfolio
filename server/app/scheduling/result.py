from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SchedulerReplyKind(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    CANCELLED = "cancelled"
    NEED_DATE = "need_date"
    INVALID_RANGE = "invalid_range"
    INVALID_SLOT = "invalid_slot"
    SLOTS = "slots"
    NO_SLOTS = "no_slots"
    MISSING_DETAILS = "missing_details"
    APPROVAL_REQUIRED = "approval_required"


class SlotOption(BaseModel):
    slot_id: str
    start: datetime
    end: datetime


class SchedulerReply(BaseModel):
    kind: SchedulerReplyKind = SchedulerReplyKind.NOT_APPLICABLE
    not_applicable: bool = False
    slots: list[SlotOption] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    subject: str | None = None
    start: datetime | None = None
