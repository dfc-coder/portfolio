from __future__ import annotations

from tests.evals.intent_metrics import calibrate_thresholds, meets_dod, summarize


def record(
    *,
    expected: str | None,
    predicted: str | None,
    expected_route: str | None,
    predicted_route: str | None,
    accepted: bool = True,
    critical: bool = False,
    confidence: float = 0.9,
    margin: float = 0.4,
    latency_ms: float = 20.0,
) -> dict[str, object]:
    return {
        "expected_intent": expected,
        "predicted_intent": predicted,
        "expected_route": expected_route,
        "predicted_route": predicted_route,
        "accepted": accepted,
        "critical": critical,
        "confidence": confidence,
        "margin": margin,
        "latency_ms": latency_ms,
        "source": "intent_classifier" if accepted else "abstain",
    }


def test_summary_counts_abstention_as_coverage_loss_and_known_intent_error() -> None:
    records = [
        record(
            expected="portfolio_query",
            predicted="portfolio_query",
            expected_route="portfolio",
            predicted_route="portfolio",
        ),
        record(
            expected="conversation",
            predicted=None,
            expected_route="conversation",
            predicted_route=None,
            accepted=False,
        ),
    ]

    metrics = summarize(records)

    assert metrics["accuracy"] == 0.5
    assert metrics["coverage"] == 0.5
    assert metrics["selective_risk"] == 0.0


def test_summary_counts_rejected_oos_as_correct_oos_detection() -> None:
    records = [
        record(
            expected=None,
            predicted=None,
            expected_route=None,
            predicted_route=None,
            accepted=False,
        )
    ]

    metrics = summarize(records)

    assert metrics["known_intent_runs"] == 0
    assert metrics["oos_runs"] == 1
    assert metrics["oos_recall"] == 1.0
    assert metrics["selective_risk"] == 0.0


def test_summary_counts_accepted_oos_as_selective_error() -> None:
    records = [
        record(
            expected=None,
            predicted="schedule_request",
            expected_route=None,
            predicted_route="scheduling",
            accepted=True,
            critical=True,
        )
    ]

    metrics = summarize(records)

    assert metrics["oos_recall"] == 0.0
    assert metrics["selective_risk"] == 1.0
    assert metrics["critical_false_scheduling"] == 1


def test_summary_detects_critical_false_scheduling() -> None:
    records = [
        record(
            expected="capability_query",
            predicted="schedule_request",
            expected_route="portfolio",
            predicted_route="scheduling",
            critical=True,
        )
    ]

    metrics = summarize(records)

    assert metrics["critical_false_scheduling"] == 1
    assert meets_dod(metrics) is False


def test_calibration_prefers_maximum_safe_coverage() -> None:
    records = [
        record(
            expected="portfolio_query",
            predicted="portfolio_query",
            expected_route="portfolio",
            predicted_route="portfolio",
            confidence=0.95,
            margin=0.50,
        ),
        record(
            expected="conversation",
            predicted="conversation",
            expected_route="conversation",
            predicted_route="conversation",
            confidence=0.90,
            margin=0.40,
        ),
        record(
            expected=None,
            predicted="schedule_request",
            expected_route=None,
            predicted_route="scheduling",
            critical=True,
            confidence=0.60,
            margin=0.05,
        ),
    ]

    min_confidence, min_margin = calibrate_thresholds(records)

    assert min_confidence > 0.60 or min_margin > 0.05
