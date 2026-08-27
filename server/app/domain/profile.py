from __future__ import annotations

import json

from pydantic import BaseModel, Field


class OwnerProfile(BaseModel):
    name: str
    headline: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    github: str | None = None
    portfolio: str | None = None
    timezone: str = "America/Argentina/Buenos_Aires"


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
    instructions: list[str] = Field(default_factory=list)

    def prompt_context(self) -> str:
        payload = {
            "owner": self.owner.model_dump(),
            "representative": self.representative.model_dump(),
            "positioning": self.positioning.model_dump(),
            "experience": [item.model_dump() for item in self.experience],
            "professional_experience": [item.model_dump() for item in self.professional_experience],
            "skills": self.skills.model_dump(),
            "services": [service.model_dump() for service in self.services],
            "projects": [project.model_dump() for project in self.projects],
            "education": [item.model_dump() for item in self.education],
            "certifications": [item.model_dump() for item in self.certifications],
            "languages": [item.model_dump() for item in self.languages],
            "business": self.business.model_dump(),
            "faq": [item.model_dump() for item in self.faq],
            "instructions": self.instructions,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
