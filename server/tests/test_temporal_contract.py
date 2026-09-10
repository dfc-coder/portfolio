import json

import pytest

from app.temporal import (
    DATETIME_REQUEST_SCHEMA,
    REMINDER_REQUEST_SCHEMA,
    _parse_datetime_request,
    _parse_reminder_request,
)


def test_datetime_contract_accepts_explicit_date_without_timezone() -> None:
    request = _parse_datetime_request(
        json.dumps(
            {
                "kind": "weekday",
                "reference_kind": "date",
                "reference": "2026-12-25",
                "offset": 0,
                "unit": "days",
                "timezone": None,
                "language": "es",
            }
        )
    )

    assert request.reference_kind == "date"
    assert request.reference == "2026-12-25"
    assert request.timezone is None


def test_datetime_contract_rejects_datetime_for_date_reference() -> None:
    with pytest.raises(RuntimeError, match="reference_kind=date requires YYYY-MM-DD"):
        _parse_datetime_request(
            json.dumps(
                {
                    "kind": "weekday",
                    "reference_kind": "date",
                    "reference": "2026-12-25T00:00:00+00:00",
                    "offset": 0,
                    "unit": "days",
                    "timezone": None,
                    "language": "es",
                }
            )
        )


def test_datetime_contract_rejects_timezone_for_date_reference() -> None:
    with pytest.raises(RuntimeError, match="reference_kind=date requires timezone=null"):
        _parse_datetime_request(
            json.dumps(
                {
                    "kind": "weekday",
                    "reference_kind": "date",
                    "reference": "2026-01-01",
                    "offset": 0,
                    "unit": "days",
                    "timezone": "Europe/Madrid",
                    "language": "es",
                }
            )
        )


def test_datetime_contract_requires_now_literal() -> None:
    with pytest.raises(RuntimeError, match="reference_kind=now requires reference='now'"):
        _parse_datetime_request(
            json.dumps(
                {
                    "kind": "date",
                    "reference_kind": "now",
                    "reference": "2026-09-09",
                    "offset": 1,
                    "unit": "days",
                    "timezone": None,
                    "language": "es",
                }
            )
        )


def test_reminder_contract_accepts_explicit_datetime() -> None:
    request = _parse_reminder_request(
        json.dumps(
            {
                "reference_kind": "datetime",
                "reference": "2026-12-01T10:30:00-03:00",
                "offset": 0,
                "unit": "days",
                "message": "Enviar la propuesta",
                "timezone": None,
                "language": "es",
            }
        )
    )

    assert request.reference_kind == "datetime"
    assert request.reference == "2026-12-01T10:30:00-03:00"


def test_model_contracts_are_closed_json_schemas() -> None:
    assert DATETIME_REQUEST_SCHEMA["additionalProperties"] is False
    assert REMINDER_REQUEST_SCHEMA["additionalProperties"] is False
    assert DATETIME_REQUEST_SCHEMA["properties"]["reference_kind"]["enum"] == [
        "now",
        "date",
        "datetime",
    ]
    assert DATETIME_REQUEST_SCHEMA["properties"]["unit"]["enum"] == [
        "minutes",
        "hours",
        "days",
        "weeks",
    ]
