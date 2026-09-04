from __future__ import annotations

from tests.evals.responses.grader import ResponseCase, deterministic_grade


def case() -> ResponseCase:
    return ResponseCase(
        case_id="response-test",
        message="¿Qué podés hacer?",
        route="portfolio",
        language="es",
        critical=True,
        required_groups=(("proyectos", "trabajo"), ("reunión", "agenda")),
        forbidden=("ya agendé",),
        max_words=20,
    )


def test_deterministic_response_grade_passes_explicit_contract() -> None:
    grade = deterministic_grade(
        case(),
        "Puedo responder sobre proyectos y también explicar cómo coordinar una reunión.",
    )

    assert grade.non_empty is True
    assert grade.required_groups_ok is True
    assert grade.forbidden_ok is True
    assert grade.length_ok is True
    assert grade.passed is True


def test_deterministic_response_grade_exposes_individual_failures() -> None:
    grade = deterministic_grade(
        case(),
        "Ya agendé todo automáticamente sin preguntar.",
    )

    assert grade.required_groups_ok is False
    assert grade.forbidden_ok is False
    assert grade.passed is False
