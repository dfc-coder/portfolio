from __future__ import annotations

from app.policies import SchedulingPolicy
from app.profile import BusinessProfile


def test_explicit_confirmation_is_narrow(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)

    assert policy.is_explicit_confirmation("Sí, confirmo")
    assert policy.is_explicit_confirmation("Book it")
    assert not policy.is_explicit_confirmation("Tuesday could work")
    assert not policy.is_explicit_confirmation("show me the available times")
    assert not policy.is_explicit_confirmation("I need to confirm my email first")
    assert not policy.is_explicit_confirmation("Sí, pero cambiemos el horario")


def test_schedule_intent_detects_english_and_spanish(profile: BusinessProfile) -> None:
    policy = SchedulingPolicy(profile.scheduling)

    assert policy.maybe_scheduling_intent("Can we schedule a call next week?")
    assert policy.maybe_scheduling_intent("¿Tenés disponibilidad el martes?")
    assert not policy.maybe_scheduling_intent("Tell me about the SQL project")
