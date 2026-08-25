from app.scheduling.admission import (
    availability_clarification,
    is_availability_request,
    is_new_scheduling_request,
)


def test_explicit_meeting_requests_are_admitted() -> None:
    assert is_new_scheduling_request("Quiero coordinar una reunión con Diego")
    assert is_new_scheduling_request("Can we schedule a call with Diego?")


def test_availability_requests_are_operational() -> None:
    assert is_availability_request("¿Qué disponibilidad tiene Diego?")
    assert is_new_scheduling_request("sobre tu disponibilidad?")
    assert is_new_scheduling_request("Are there any available slots tomorrow?")
    assert "agenda de Diego" in availability_clarification("sobre tu disponibilidad?")


def test_dates_and_business_questions_are_not_operational_intents() -> None:
    assert not is_new_scheduling_request("El 25 de agosto")
    assert not is_new_scheduling_request(
        "Quiero información sobre la experiencia de Diego"
    )
    assert not is_new_scheduling_request("¿Qué hora es?")
