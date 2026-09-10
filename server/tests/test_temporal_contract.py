import json

import pytest

from app.temporal import (
    DATETIME_REQUEST_SCHEMA,
    REMINDER_REQUEST_SCHEMA,
    _parse_datetime_request,
    _parse_reminder_request,
)


def test_datetime_contract_accepts_explicit_date() -> None:
    request = _parse_datetime_request(
        json.dumps(
            {
                "kind": "weekday",
                "reference": "2026-12-25",
                "offset": 0,
                "unit": "days",
                "language": "es",
            }
        )
    )

    assert request.reference == "2026-12-25"
    assert request.timezone is None


def test_datetime_contract_canonicalizes_midnight_datetime_to_date() -> None:
    request = _parse_datetime_request(
        json.dumps(
            {
                "kind": "weekday",
                "reference": "2026-12-25T00:00:00+00:00",
                "offset": 0,
                "unit": "days",
                "timezone": "UTC",
                "language": "es",
            }
        )
    )

    assert request.reference == "2026-12-25"
    assert request.timezone is None


def test_datetime_contract_drops_timezone_from_date_anchor() -> None:
    request = _parse_datetime_request(
        json.dumps(
            {
                "kind": "weekday",
                "reference": "2026-01-01",
                "offset": 0,
                "unit": "days",
                "timezone": "Europe/Madrid",
                "language": "es",
            }
        )
    )

    assert request.reference == "2026-01-01"
    assert request.timezone is None


def test_datetime_contract_preserves_real_datetime() -> None:
    request = _parse_datetime_request(
        json.dumps(
            {
                "kind": "datetime",
                "reference": "2026-12-01T10:30:00-03:00",
                "offset": 0,
                "unit": "days",
                "language": "es",
            }
        )
    )

    assert request.reference == "2026-12-01T10:30:00-03:00"


def test_datetime_contract_rejects_invalid_reference() -> None:
    with pytest.raises(RuntimeError, match="valid ISO-8601"):
        _parse_datetime_request(
            json.dumps(
                {
                    "kind": "date",
                    "reference": "not-a-date",
                    "offset": 0,
                    "unit": "days",
                    "language": "es",
                }
            )
        )


def test_reminder_contract_accepts_relative_request() -> None:
    request = _parse_reminder_request(
        json.dumps(
            {
                "reference": "now",
                "offset": 2,
                "unit": "hours",
                "message": "Enviar el CV",
                "language": "es",
            }
        )
    )

    assert request.reference == "now"
    assert request.offset == 2
    assert request.unit == "hours"


def test_reminder_contract_accepts_explicit_datetime() -> None:
    request = _parse_reminder_request(
        json.dumps(
            {
                "reference": "2026-12-01T10:30:00-03:00",
                "offset": 0,
                "unit": "days",
                "message": "Enviar la propuesta",
                "language": "es",
            }
        )
    )

    assert request.reference == "2026-12-01T10:30:00-03:00"


def test_model_contracts_are_closed_and_small() -> None:
    assert DATETIME_REQUEST_SCHEMA["additionalProperties"] is False
    assert REMINDER_REQUEST_SCHEMA["additionalProperties"] is False
    assert "reference_kind" not in DATETIME_REQUEST_SCHEMA["properties"]
    assert "reference_kind" not in REMINDER_REQUEST_SCHEMA["properties"]
    assert DATETIME_REQUEST_SCHEMA["properties"]["unit"]["enum"] == [
        "minutes",
        "hours",
        "days",
        "weeks",
    ]
    assert REMINDER_REQUEST_SCHEMA["properties"]["unit"]["enum"] == [
        "minutes",
        "hours",
        "days",
        "weeks",
    ]
