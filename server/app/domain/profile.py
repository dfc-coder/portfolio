from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OwnerProfile(BaseModel):
    name: str
    headline: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    github: str | None = None
    portfolio: str | None = None


class RepresentativeProfile(BaseModel):
    label: str = "Business Representative"
    disclosure: str


class PositioningProfile(BaseModel):
    summary: str
    differentiators: list[str] = Field(default_factory=list)


class ExperienceAreaProfile(BaseModel):
    name: str
    summary: str


class ProfessionalRoleProfile(BaseModel):
    title: str
    company: str
    period: str
    highlights: list[str] = Field(default_factory=list)


class SkillsProfile(BaseModel):
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    ai: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    cloud_and_delivery: list[str] = Field(default_factory=list)
    security_and_reliability: list[str] = Field(default_factory=list)
    testing_and_quality: list[str] = Field(default_factory=list)
    architecture: list[str] = Field(default_factory=list)


class ServiceProfile(BaseModel):
    name: str
    description: str


class ProjectProfile(BaseModel):
    name: str
    summary: str
    stack: list[str] = Field(default_factory=list)
    outcome: str | None = None
    source_url: str | None = None


class EducationProfile(BaseModel):
    program: str
    institution: str
    period: str | None = None
    status: str | None = None


class CertificationProfile(BaseModel):
    name: str


class LanguageProfile(BaseModel):
    language: str
    level: str


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
    professional_experience: list[ProfessionalRoleProfile] = Field(default_factory=list)
    skills: SkillsProfile = Field(default_factory=SkillsProfile)
    services: list[ServiceProfile]
    projects: list[ProjectProfile]
    education: list[EducationProfile] = Field(default_factory=list)
    certifications: list[CertificationProfile] = Field(default_factory=list)
    languages: list[LanguageProfile] = Field(default_factory=list)
    business: BusinessInfoProfile = Field(default_factory=BusinessInfoProfile)
    faq: list[FaqProfile] = Field(default_factory=list)
    scheduling: SchedulingProfile
    instructions: list[str] = Field(default_factory=list)
