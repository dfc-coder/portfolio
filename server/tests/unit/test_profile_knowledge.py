from __future__ import annotations

from app.domain.profile import BusinessProfile


def test_business_profile_contains_cv_backed_rust_and_go_projects(profile: BusinessProfile) -> None:
    projects = {project.name: project for project in profile.projects}

    assert "Rust" in profile.skills.programming_languages
    assert "Go" in profile.skills.programming_languages
    assert "PocketTrace" in projects
    assert "Rust" in projects["PocketTrace"].stack
    assert "ecTask" in projects
    assert "Rust" in projects["ecTask"].stack
    assert "System-G (Growntrol)" in projects
    assert "Rust" in projects["System-G (Growntrol)"].stack
    assert "Xarlatan" in projects
    assert "Go" in projects["Xarlatan"].stack


def test_prompt_context_exposes_cv_experience_and_credentials(profile: BusinessProfile) -> None:
    context = profile.prompt_context()

    assert "FK Tech" in context
    assert "AiRoss" in context
    assert "LangGraph" in context
    assert "Deep Research with LangGraph" in context
    assert "OWASP Top 10 Secure Coding" in context
    assert "PocketTrace" in context
    assert "System-G (Growntrol)" in context
