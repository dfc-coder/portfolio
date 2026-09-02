from __future__ import annotations

import json

import pytest

from app.domain.routing import Intent
from app.infrastructure.intent_classifier import (
    IntentClassifier,
    IntentModel,
    load_intent_model,
)


def model() -> IntentModel:
    return IntentModel(
        version=1,
        embedding_model="test-embedding",
        embedding_dimension=2,
        intents=(
            Intent.PORTFOLIO_QUERY,
            Intent.CAPABILITY_QUERY,
            Intent.SCHEDULE_REQUEST,
        ),
        coefficients=(
            (2.0, 0.0),
            (0.0, 2.0),
            (-2.0, -2.0),
        ),
        intercepts=(0.0, 0.0, 0.0),
        min_confidence=0.60,
        min_margin=0.10,
        training_dataset_hash="abc123",
        seed=42,
    )


def test_classifier_returns_highest_probability_intent() -> None:
    prediction = IntentClassifier(model()).predict([1.0, 0.0])

    assert prediction.intent == Intent.PORTFOLIO_QUERY
    assert prediction.confidence > 0.5
    assert prediction.margin > 0.0


def test_classifier_probabilities_sum_to_one() -> None:
    prediction = IntentClassifier(model()).predict([0.2, 0.3])

    assert sum(prediction.scores.values()) == pytest.approx(1.0)


def test_classifier_rejects_wrong_embedding_dimension() -> None:
    classifier = IntentClassifier(model())

    with pytest.raises(ValueError, match="dimension mismatch"):
        classifier.predict([1.0, 2.0, 3.0])


def test_classifier_applies_model_thresholds() -> None:
    classifier = IntentClassifier(model())
    prediction = classifier.predict([1.0, 0.0])

    assert classifier.accepts(prediction) is True


def test_load_model_rejects_mismatched_coefficient_dimension(tmp_path) -> None:
    artifact = {
        "version": 1,
        "embedding_model": "test",
        "embedding_dimension": 3,
        "intents": [
            "portfolio_query",
            "capability_query",
            "conversation",
        ],
        "coefficients": [
            [1.0, 2.0],
            [2.0, 3.0],
            [0.0, 1.0],
        ],
        "intercepts": [0.0, 0.0, 0.0],
        "min_confidence": 0.7,
        "min_margin": 0.1,
        "training_dataset_hash": "abc",
        "seed": 42,
    }
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="dimension"):
        load_intent_model(path)


def test_load_model_rejects_unknown_intent(tmp_path) -> None:
    artifact = {
        "version": 1,
        "embedding_model": "test",
        "embedding_dimension": 1,
        "intents": ["portfolio_query", "not_a_real_intent"],
        "coefficients": [[1.0], [0.0]],
        "intercepts": [0.0, 0.0],
        "min_confidence": 0.7,
        "min_margin": 0.1,
        "training_dataset_hash": "abc",
        "seed": 42,
    }
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid intent model artifact"):
        load_intent_model(path)
