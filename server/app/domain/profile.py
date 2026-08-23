from __future__ import annotations

import json
from datetime import time
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OwnerProfile(BaseModel):
    name: str
    headline: str
    location: str | None = None


class RepresentativeProfile(BaseModel):
    label: str = "Business Representative"
    disclosure: str


class PositioningProfile(BaseModel):
    summary: str
    differentiators: list[str] = Field(default_factory=list)


class ExperienceAreaProfile(BaseModel):
    name: str
    summary: str


class SkillsProfile(BaseModel):
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    ai: list[str] = Field(default_factory=list)
    cloud_and_delivery: list[str] = Field(default_factory=list)
    architecture: list[str] = Field(default_factory=list)


class ServiceProfile(BaseModel):
    name: str
    description: str


class ProjectProfile(BaseModel):
    name: str
    summary: str
    stack: list[str] = Field(default_factory=list)
    outcome: str | None = None


class BusinessInfoProfile(BaseModel):
    collaboration_modes: list[str] = Field(default_factory=list)
    project_types: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)


class FaqProfile(BaseModel):
    question: str
    answer: str


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
    positioning: PositioningProfile
    experience: list[ExperienceAreaProfile] = Field(default_factory=list)
    skills: SkillsProfile = Field(default_factory=SkillsProfile)
    services: list[ServiceProfile]
    projects: list[ProjectProfile]
    business: BusinessInfoProfile = Field(default_factory=BusinessInfoProfile)
    faq: list[FaqProfile] = Field(default_factory=list)
    scheduling: SchedulingProfile
    instructions: list[str] = Field(default_factory=list)

    def prompt_context(self) -> str:
        payload = {
            "owner": self.owner.model_dump(),
            "representative": self.representative.model_dump(),
            "positioning": self.positioning.model_dump(),
            "experience": [item.model_dump() for item in self.experience],
            "skills": self.skills.model_dump(),
            "services": [service.model_dump() for service in self.services],
            "projects": [project.model_dump() for project in self.projects],
            "business": self.business.model_dump(),
            "faq": [item.model_dump() for item in self.faq],
            "instructions": self.instructions,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
