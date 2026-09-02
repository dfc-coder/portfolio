from __future__ import annotations

from tests.evals.intent_metrics import calibrate_thresholds, meets_dod, summarize


def record(
    *,
    expected_route: str | None,
    predicted_route: str | None,
    accepted: bool = True,
    critical: bool = False,
    confidence: float = 0.9,
    margin: float = 0.4,
    latency_ms: float = 20.0,
    active_workflow: str | None = None,
) -> dict[str, object]:
    return {
        "expected_intent": None,
        "predicted_intent": None,
        "expected_route": expected_route,
        "predicted_route": predicted_route,
        "accepted": accepted,
        "critical": critical,
        "confidence": confidence,
        "margin": margin,
        "latency_ms": latency_ms,
        "active_workflow": active_workflow,
        "source": "route_classifier" if accepted else "abstain",
    }


def test_summary_counts_abstention_as_coverage_loss_and_route_error() -> None:
    records = [
        record(
            expected_route="portfolio",
            predicted_route="portfolio",
        ),
        record(
            expected_route="conversation",
            predicted_route=None,
            accepted=False,
        ),
    ]

    metrics = summarize(records)

    assert metrics["route_accuracy"] == 0.5
    assert metrics["coverage"] == 0.5
    assert metrics["route_selective_risk"] == 0.0


def test_summary_counts_rejected_oos_as_correct_oos_detection() -> None:
    records = [
        record(
            expected_route=None,
            predicted_route=None,
            accepted=False,
        )
    ]

    metrics = summarize(records)

    assert metrics["known_route_runs"] == 0
    assert metrics["oos_runs"] == 1
    assert metrics["oos_recall"] == 1.0
    assert metrics["route_selective_risk"] == 0.0


def test_summary_counts_accepted_oos_as_selective_error() -> None:
    records = [
        record(
            expected_route=None,
            predicted_route="scheduling",
            accepted=True,
            critical=True,
        )
    ]

    metrics = summarize(records)

    assert metrics["oos_recall"] == 0.0
    assert metrics["route_selective_risk"] == 1.0
    assert metrics["critical_false_scheduling"] == 1


def test_summary_does_not_penalize_leaf_intent_when_business_route_is_correct() -> None:
    records = [
        {
            **record(
                expected_route="portfolio",
                predicted_route="portfolio",
            ),
            "expected_intent": "portfolio_query",
            "predicted_intent": "capability_query",
        }
    ]

    metrics = summarize(records)

    assert metrics["route_accuracy"] == 1.0
    assert metrics["route_selective_risk"] == 0.0


def test_summary_detects_critical_false_scheduling() -> None:
    records = [
        record(
            expected_route="portfolio",
            predicted_route="scheduling",
            critical=True,
        )
    ]

    metrics = summarize(records)

    assert metrics["critical_false_scheduling"] == 1
    assert meets_dod(metrics) is False


def test_calibration_uses_distinct_business_context_thresholds() -> None:
    records = [
        record(
            expected_route="portfolio",
            predicted_route="portfolio",
            confidence=0.45,
            margin=0.20,
        ),
        record(
            expected_route="conversation",
            predicted_route="conversation",
            confidence=0.50,
            margin=0.20,
        ),
        record(
            expected_route="scheduling",
            predicted_route="scheduling",
            confidence=0.75,
            margin=0.30,
        ),
        record(
            expected_route="scheduling",
            predicted_route="scheduling",
            confidence=0.40,
            margin=0.10,
            active_workflow="scheduling",
        ),
        record(
            expected_route=None,
            predicted_route="scheduling",
            critical=True,
            confidence=0.60,
            margin=0.05,
        ),
    ]

    thresholds = calibrate_thresholds(records)

    assert set(thresholds) == {
        "conversation",
        "portfolio",
        "scheduling",
        "scheduling_active",
    }
    scheduling_confidence, scheduling_margin = thresholds["scheduling"]
    assert scheduling_confidence > 0.60 or scheduling_margin > 0.05
    active_confidence, active_margin = thresholds["scheduling_active"]
    assert active_confidence <= 0.40
    assert active_margin <= 0.10
