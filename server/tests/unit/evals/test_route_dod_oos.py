from __future__ import annotations

from tests.evals.intent_metrics import meets_dod


def test_dod_requires_oos_recall_when_oos_cases_are_present() -> None:
    metrics = {
        "route_accuracy": 1.0,
        "route_macro_f1": 1.0,
        "critical_false_scheduling": 0,
        "route_selective_risk": 0.0,
        "oos_recall": 0.5,
        "latency_ms": {"p95": 10.0},
    }

    assert meets_dod(metrics) is False


def test_dod_allows_no_oos_metric_for_challenge_sets_without_oos() -> None:
    metrics = {
        "route_accuracy": 1.0,
        "route_macro_f1": 1.0,
        "critical_false_scheduling": 0,
        "route_selective_risk": 0.0,
        "oos_recall": None,
        "latency_ms": {"p95": 10.0},
    }

    assert meets_dod(metrics) is True
