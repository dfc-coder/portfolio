from __future__ import annotations

import json

import pytest

from app.domain.routing import Route
from app.infrastructure.business_route_classifier import (
    BusinessRouteClassifier,
    RouteModel,
    RouteThreshold,
    load_route_model,
)


def model() -> RouteModel:
    return RouteModel(
        version=4,
        embedding_model="test-embedding",
        embedding_dimension=2,
        routes=(
            Route.PORTFOLIO,
            Route.SCHEDULING,
            Route.CONVERSATION,
        ),
        coefficients=(
            (2.0, 0.0),
            (0.0, 2.0),
            (-2.0, -2.0),
        ),
        intercepts=(0.0, 0.0, 0.0),
        thresholds={
            "portfolio": RouteThreshold(0.60, 0.10),
            "scheduling": RouteThreshold(0.95, 0.20),
            "scheduling_active": RouteThreshold(0.40, 0.05),
            "conversation": RouteThreshold(0.60, 0.10),
        },
        scheduling_boundary_coefficients=(0.0, 4.0),
        scheduling_boundary_intercept=-2.0,
        scheduling_boundary_threshold=RouteThreshold(0.60, 0.10),
        training_dataset_hash="abc123",
        seed=42,
    )


def test_classifier_returns_highest_probability_route() -> None:
    prediction = BusinessRouteClassifier(model()).predict([1.0, 0.0])

    assert prediction.route == Route.PORTFOLIO
    assert prediction.confidence > 0.5
    assert prediction.margin > 0.0


def test_classifier_probabilities_sum_to_one() -> None:
    prediction = BusinessRouteClassifier(model()).predict([0.2, 0.3])

    assert sum(prediction.scores.values()) == pytest.approx(1.0)


def test_classifier_rejects_wrong_embedding_dimension() -> None:
    classifier = BusinessRouteClassifier(model())

    with pytest.raises(ValueError, match="dimension mismatch"):
        classifier.predict([1.0, 2.0, 3.0])


def test_classifier_applies_route_threshold() -> None:
    classifier = BusinessRouteClassifier(model())
    prediction = classifier.predict([1.0, 0.0])

    assert classifier.accepts(prediction, active_scheduling=False) is True


def test_scheduling_active_can_use_distinct_threshold() -> None:
    classifier = BusinessRouteClassifier(model())
    prediction = classifier.predict([0.0, 1.0])

    assert prediction.route == Route.SCHEDULING
    assert classifier.accepts(prediction, active_scheduling=True) is True
    assert classifier.accepts(prediction, active_scheduling=False) is False


def test_scheduling_boundary_distinguishes_capability_from_action() -> None:
    classifier = BusinessRouteClassifier(model())

    capability = classifier.predict_scheduling_boundary([1.0, 0.0])
    action = classifier.predict_scheduling_boundary([0.0, 1.0])

    assert capability.is_capability is True
    assert classifier.accepts_capability_override(capability) is True
    assert action.is_capability is False
    assert classifier.accepts_capability_override(action) is False


def test_load_model_rejects_mismatched_coefficient_dimension(tmp_path) -> None:
    artifact = {
        "version": 4,
        "embedding_model": "test",
        "embedding_dimension": 3,
        "routes": ["portfolio", "scheduling", "conversation"],
        "coefficients": [
            [1.0, 2.0],
            [2.0, 3.0],
            [0.0, 1.0],
        ],
        "intercepts": [0.0, 0.0, 0.0],
        "thresholds": {
            "portfolio": {"min_confidence": 0.4, "min_margin": 0.1},
            "scheduling": {"min_confidence": 0.7, "min_margin": 0.2},
            "scheduling_active": {"min_confidence": 0.4, "min_margin": 0.1},
            "conversation": {"min_confidence": 0.4, "min_margin": 0.1},
        },
        "scheduling_boundary_coefficients": [1.0, 2.0],
        "scheduling_boundary_intercept": 0.0,
        "scheduling_boundary_threshold": {"min_confidence": 0.6, "min_margin": 0.1},
        "training_dataset_hash": "abc",
        "seed": 42,
    }
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="dimension"):
        load_route_model(path)


def test_load_model_rejects_unknown_route(tmp_path) -> None:
    artifact = {
        "version": 4,
        "embedding_model": "test",
        "embedding_dimension": 1,
        "routes": ["portfolio", "not_a_real_route"],
        "coefficients": [[1.0], [0.0]],
        "intercepts": [0.0, 0.0],
        "thresholds": {
            "portfolio": {"min_confidence": 0.4, "min_margin": 0.1},
            "scheduling": {"min_confidence": 0.7, "min_margin": 0.2},
            "scheduling_active": {"min_confidence": 0.4, "min_margin": 0.1},
            "conversation": {"min_confidence": 0.4, "min_margin": 0.1},
        },
        "scheduling_boundary_coefficients": [1.0],
        "scheduling_boundary_intercept": 0.0,
        "scheduling_boundary_threshold": {"min_confidence": 0.6, "min_margin": 0.1},
        "training_dataset_hash": "abc",
        "seed": 42,
    }
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid route model artifact"):
        load_route_model(path)
