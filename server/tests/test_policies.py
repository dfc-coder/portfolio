from __future__ import annotations

from app.domain.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy


def test_explicit_confirmation_is_narrow(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)

    assert policy.is_explicit_confirmation("Sí, confirmo")
    assert policy.is_explicit_confirmation("Book it")
    assert not policy.is_explicit_confirmation("Tuesday could work")
    assert not policy.is_explicit_confirmation("show me the available times")
    assert not policy.is_explicit_confirmation("I need to confirm my email first")
    assert not policy.is_explicit_confirmation("Sí, pero cambiemos el horario")


def test_rejection_only_cancels_explicit_scheduling_language(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)

    assert policy.is_rejection("cancel")
    assert policy.is_rejection("no agendes")
    assert not policy.is_rejection("¿En qué tecnologías trabaja Diego?")
    assert not policy.is_rejection("No tengo email todavía")
    assert not policy.is_rejection("No sé qué horario prefiero")
