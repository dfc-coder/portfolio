from __future__ import annotations

import json
from datetime import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OwnerProfile(BaseModel):
    name: str
    headline: str
    location: str | None = None


class RepresentativeProfile(BaseModel):
    label: str = "Business Representative"
    disclosure: str


class ServiceProfile(BaseModel):
    name: str
    description: str


class ProjectProfile(BaseModel):
    name: str
    summary: str
    stack: list[str] = Field(default_factory=list)


class SchedulingProfile(BaseModel):
    timezone: str
    meeting_minutes: int = Field(default=30, ge=15, le=120)
    buffer_minutes: int = Field(default=15, ge=0, le=60)
    min_notice_hours: int = Field(default=4, ge=0, le=168)
    max_days_ahead: int = Field(default=30, ge=1, le=180)
    max_slots: int = Field(default=6, ge=1, le=12)
    business_hours: dict[str, tuple[time, time]]

    @field_validator("business_hours", mode="before")
    @classmethod
    def parse_business_hours(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        parsed: dict[str, tuple[str, str]] = {}
        for day, hours in value.items():
            if not isinstance(hours, list) or len(hours) != 2:
                raise ValueError(f"business_hours.{day} must be [start, end]")
            parsed[day] = (hours[0], hours[1])
        return parsed


class BusinessProfile(BaseModel):
    owner: OwnerProfile
    representative: RepresentativeProfile
    services: list[ServiceProfile]
    projects: list[ProjectProfile]
    scheduling: SchedulingProfile
    instructions: list[str] = Field(default_factory=list)

    def prompt_context(self) -> str:
        payload = {
            "owner": self.owner.model_dump(),
            "services": [service.model_dump() for service in self.services],
            "projects": [project.model_dump() for project in self.projects],
            "instructions": self.instructions,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def load_business_profile(path: Path) -> BusinessProfile:
    with path.open("r", encoding="utf-8") as handle:
        return BusinessProfile.model_validate(json.load(handle))
