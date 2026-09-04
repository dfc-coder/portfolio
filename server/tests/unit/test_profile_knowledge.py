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
