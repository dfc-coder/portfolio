from __future__ import annotations

import json

from app.domain.routing import Route
from app.infrastructure.nonlinear_route_classifier import (
    DecisionThreshold,
    NonlinearRouteClassifier,
    NonlinearRouteModel,
    load_nonlinear_route_model,
    save_nonlinear_route_model,
)


def model() -> NonlinearRouteModel:
    zero = DecisionThreshold(0.0, 0.0)
    return NonlinearRouteModel(
        version=5,
        embedding_model="test",
        embedding_dimension=2,
        labels=("conversation", "oos", "portfolio", "scheduling"),
        hidden_weights=((1.0, 0.0), (0.0, 1.0)),
        hidden_bias=(0.0, 0.0),
        output_weights=((0.0, -3.0, 3.0, 0.0), (0.0, -3.0, 0.0, 3.0)),
        output_bias=(0.0, 0.0, 0.0, 0.0),
        thresholds={
            "conversation": zero,
            "portfolio": zero,
            "scheduling": zero,
            "scheduling_active": zero,
        },
        training_dataset_hash="abc",
        seed=42,
    )


def test_predicts_business_route_from_mlp() -> None:
    prediction = NonlinearRouteClassifier(model()).predict([1.0, 0.0])

    assert prediction.label == "portfolio"
    assert prediction.route == Route.PORTFOLIO
    assert prediction.confidence > 0.5


def test_predicts_explicit_oos_as_no_route() -> None:
    classifier = NonlinearRouteClassifier(model())
    prediction = classifier.predict([-1.0, -1.0])

    assert prediction.label == "oos"
    assert prediction.route is None
    assert classifier.accepts(prediction, active_scheduling=False) is False


def test_round_trip_model_artifact(tmp_path) -> None:
    path = tmp_path / "route-v5.json"
    save_nonlinear_route_model(model(), path)

    loaded = load_nonlinear_route_model(path)

    assert loaded == model()


def test_rejects_invalid_artifact_shape(tmp_path) -> None:
    payload = {
        "version": 5,
        "embedding_model": "test",
        "embedding_dimension": 2,
        "labels": ["conversation", "oos", "portfolio", "scheduling"],
        "hidden_weights": [[1.0], [1.0]],
        "hidden_bias": [0.0, 0.0],
        "output_weights": [[1.0, 1.0, 1.0, 1.0]],
        "output_bias": [0.0, 0.0, 0.0, 0.0],
        "thresholds": {
            "conversation": {"min_confidence": 0.0, "min_margin": 0.0},
            "portfolio": {"min_confidence": 0.0, "min_margin": 0.0},
            "scheduling": {"min_confidence": 0.0, "min_margin": 0.0},
            "scheduling_active": {"min_confidence": 0.0, "min_margin": 0.0},
        },
        "training_dataset_hash": "abc",
        "seed": 42,
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_nonlinear_route_model(path)
    except ValueError as exc:
        assert "hidden weight width" in str(exc)
    else:
        raise AssertionError("invalid nonlinear artifact should fail")
