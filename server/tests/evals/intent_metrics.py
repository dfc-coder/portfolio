from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from app.domain.routing import Route


DOD_MIN_ROUTE_ACCURACY = 0.95
DOD_MIN_ROUTE_MACRO_F1 = 0.95
DOD_MAX_ROUTE_SELECTIVE_RISK = 0.02
DOD_MAX_ROUTING_P95_MS = 100.0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def route_macro_f1(records: list[dict[str, Any]]) -> float:
    scores: list[float] = []
    for route in Route:
        label = route.value
        true_positive = sum(
            record["expected_route"] == label
            and record["predicted_route"] == label
            for record in records
        )
        false_positive = sum(
            record["expected_route"] != label
            and record["predicted_route"] == label
            for record in records
        )
        false_negative = sum(
            record["expected_route"] == label
            and record["predicted_route"] != label
            for record in records
        )
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = (
            true_positive / precision_denominator
            if precision_denominator
            else 0.0
        )
        recall = true_positive / recall_denominator if recall_denominator else 0.0
        scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    return sum(scores) / len(scores) if scores else 0.0


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    known = [record for record in records if record["expected_route"] is not None]
    out_of_scope = [record for record in records if record["expected_route"] is None]
    accepted = [record for record in records if record["accepted"]]
    correct_known = [
        record
        for record in known
        if record["predicted_route"] == record["expected_route"]
    ]
    accepted_route_errors = [
        record
        for record in accepted
        if record["expected_route"] is None
        or record["predicted_route"] != record["expected_route"]
    ]
    correctly_rejected_oos = [
        record
        for record in out_of_scope
        if not record["accepted"]
    ]
    non_scheduling = [
        record
        for record in records
        if record["expected_route"] != Route.SCHEDULING.value
    ]
    false_scheduling = [
        record
        for record in non_scheduling
        if record["predicted_route"] == Route.SCHEDULING.value
    ]
    critical_false_scheduling = [
        record
        for record in false_scheduling
        if record["critical"]
    ]
    latencies = [float(record["latency_ms"]) for record in records]
    route_confusion = Counter(
        (
            record["expected_route"] or "oos",
            record["predicted_route"] or "abstain",
        )
        for record in records
    )

    return {
        "runs": total,
        "known_route_runs": len(known),
        "oos_runs": len(out_of_scope),
        "route_accuracy": (
            round(len(correct_known) / len(known), 4)
            if known
            else 1.0
        ),
        "route_macro_f1": round(route_macro_f1(records), 4) if known else 1.0,
        "coverage": round(len(accepted) / total, 4) if total else 1.0,
        "route_selective_risk": (
            round(len(accepted_route_errors) / len(accepted), 4)
            if accepted
            else 0.0
        ),
        "oos_recall": (
            round(len(correctly_rejected_oos) / len(out_of_scope), 4)
            if out_of_scope
            else None
        ),
        "false_scheduling_rate": (
            round(len(false_scheduling) / len(non_scheduling), 4)
            if non_scheduling
            else 0.0
        ),
        "critical_false_scheduling": len(critical_false_scheduling),
        "source_counts": dict(Counter(record["source"] for record in records)),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "route_confusion_matrix": {
            f"{expected}->{predicted}": count
            for (expected, predicted), count in sorted(route_confusion.items())
        },
        "failures": [
            record
            for record in records
            if (
                record["expected_route"] is None and record["accepted"]
            )
            or (
                record["expected_route"] is not None
                and record["predicted_route"] != record["expected_route"]
            )
        ],
    }


def meets_dod(metrics: dict[str, Any]) -> bool:
    return (
        metrics["route_accuracy"] >= DOD_MIN_ROUTE_ACCURACY
        and metrics["route_macro_f1"] >= DOD_MIN_ROUTE_MACRO_F1
        and metrics["critical_false_scheduling"] == 0
        and metrics["route_selective_risk"] <= DOD_MAX_ROUTE_SELECTIVE_RISK
        and metrics["latency_ms"]["p95"] <= DOD_MAX_ROUTING_P95_MS
    )


def calibrate_thresholds(
    records: list[dict[str, Any]],
    *,
    max_selective_risk: float = DOD_MAX_ROUTE_SELECTIVE_RISK,
) -> tuple[float, float]:
    """Maximize validation coverage under business-route safety constraints."""
    confidence_candidates = sorted(
        {0.0, *(float(record["confidence"]) for record in records)}
    )
    margin_candidates = sorted(
        {0.0, *(float(record["margin"]) for record in records)}
    )
    best: tuple[float, float, float, float] | None = None
    chosen: tuple[float, float] | None = None

    for min_confidence in confidence_candidates:
        for min_margin in margin_candidates:
            accepted = [
                record
                for record in records
                if record["confidence"] >= min_confidence
                and record["margin"] >= min_margin
            ]
            if not accepted:
                continue
            errors = [
                record
                for record in accepted
                if record["expected_route"] is None
                or record["predicted_route"] != record["expected_route"]
            ]
            critical_false_scheduling = sum(
                bool(record["critical"])
                and record["expected_route"] != Route.SCHEDULING.value
                and record["predicted_route"] == Route.SCHEDULING.value
                for record in accepted
            )
            selective_risk = len(errors) / len(accepted)
            if selective_risk > max_selective_risk or critical_false_scheduling:
                continue
            coverage = len(accepted) / len(records) if records else 1.0
            candidate = (
                coverage,
                -selective_risk,
                -min_confidence,
                -min_margin,
            )
            if best is None or candidate > best:
                best = candidate
                chosen = (min_confidence, min_margin)

    if best is None or chosen is None:
        raise ValueError("validation data cannot satisfy route-risk safety constraints")
    return chosen
