from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.domain.routing import Route
from app.infrastructure.nonlinear_route_classifier import (
    DecisionThreshold,
    NonlinearRouteClassifier,
    NonlinearRouteModel,
    OOS_LABEL,
    save_nonlinear_route_model,
)
from tests.evals.intent_metrics import calibrate_thresholds, summarize


DEFAULT_SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the nonlinear four-class route model.")
    parser.add_argument("--train-vectors", type=Path, required=True)
    parser.add_argument("--oos-vectors", type=Path, required=True)
    parser.add_argument("--validation-vectors", type=Path, required=True)
    parser.add_argument("--train-cases", type=Path, required=True)
    parser.add_argument("--oos-cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def load_vectors(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = str(payload["embedding_model"])
    records = list(payload["records"])
    if not records:
        raise ValueError(f"no embedded records in {path}")
    dimension = len(records[0]["embedding"])
    if dimension < 1 or any(len(record["embedding"]) != dimension for record in records):
        raise ValueError(f"inconsistent embedding dimensions in {path}")
    return model, records


def training_label(record: dict[str, Any]) -> str:
    route = record.get("route")
    return str(route) if route is not None else OOS_LABEL


def balance_records(records: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[training_label(record)].append(record)
    expected = {
        Route.CONVERSATION.value,
        Route.PORTFOLIO.value,
        Route.SCHEDULING.value,
        OOS_LABEL,
    }
    if set(groups) != expected:
        raise ValueError(f"training labels must be exactly {sorted(expected)}")

    target = max(len(group) for group in groups.values())
    balanced = [
        group[index % len(group)]
        for label in sorted(groups)
        for group in [groups[label]]
        for index in range(target)
    ]
    random.Random(seed).shuffle(balanced)
    return balanced


def prediction_record(
    classifier: NonlinearRouteClassifier,
    record: dict[str, Any],
    *,
    apply_thresholds: bool,
) -> dict[str, Any]:
    prediction = classifier.predict([float(value) for value in record["embedding"]])
    active = record.get("active_workflow") == "scheduling"
    accepted = (
        classifier.accepts(prediction, active_scheduling=active)
        if apply_thresholds
        else prediction.route is not None
    )
    predicted_route = prediction.route.value if accepted and prediction.route is not None else None
    return {
        "expected_intent": record.get("intent"),
        "predicted_intent": None,
        "expected_route": record.get("route"),
        "predicted_route": predicted_route,
        "accepted": accepted,
        "critical": bool(record.get("critical", False)),
        "active_workflow": record.get("active_workflow"),
        "confidence": prediction.confidence,
        "margin": prediction.margin,
        "latency_ms": 0.0,
        "source": (
            "oos_classifier"
            if prediction.route is None
            else "nonlinear_route_classifier" if accepted else "abstain"
        ),
    }


def dataset_hash(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    train_model, train = load_vectors(args.train_vectors)
    oos_model, oos = load_vectors(args.oos_vectors)
    validation_model, validation = load_vectors(args.validation_vectors)
    if len({train_model, oos_model, validation_model}) != 1:
        raise ValueError("train, OOS and validation embeddings use different models")
    if any(record.get("route") is None for record in train):
        raise ValueError("main train split must contain only known business routes")
    if any(record.get("route") is not None for record in oos):
        raise ValueError("OOS training split must contain only route=null records")

    try:
        from sklearn.neural_network import MLPClassifier
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required only for offline nonlinear training; "
            "run this script with `uv run --with scikit-learn`"
        ) from exc

    balanced = balance_records(train + oos, args.seed)
    x_train = [[float(value) for value in record["embedding"]] for record in balanced]
    y_train = [training_label(record) for record in balanced]
    dimension = len(x_train[0])

    estimator = MLPClassifier(
        hidden_layer_sizes=(16,),
        activation="tanh",
        solver="lbfgs",
        alpha=0.5,
        max_iter=3000,
        random_state=args.seed,
    )
    estimator.fit(x_train, y_train)

    labels = tuple(str(value) for value in estimator.classes_)
    expected_labels = {
        Route.CONVERSATION.value,
        Route.PORTFOLIO.value,
        Route.SCHEDULING.value,
        OOS_LABEL,
    }
    if set(labels) != expected_labels:
        raise ValueError(f"trained labels do not match expected labels: {labels}")
    if len(estimator.coefs_) != 2 or len(estimator.intercepts_) != 2:
        raise ValueError("only one hidden layer is supported by runtime inference")

    zero_thresholds = {
        Route.CONVERSATION.value: DecisionThreshold(0.0, 0.0),
        Route.PORTFOLIO.value: DecisionThreshold(0.0, 0.0),
        Route.SCHEDULING.value: DecisionThreshold(0.0, 0.0),
        "scheduling_active": DecisionThreshold(0.0, 0.0),
    }
    uncalibrated = NonlinearRouteModel(
        version=5,
        embedding_model=train_model,
        embedding_dimension=dimension,
        labels=labels,
        hidden_weights=tuple(
            tuple(float(value) for value in row)
            for row in estimator.coefs_[0].tolist()
        ),
        hidden_bias=tuple(float(value) for value in estimator.intercepts_[0].tolist()),
        output_weights=tuple(
            tuple(float(value) for value in row)
            for row in estimator.coefs_[1].tolist()
        ),
        output_bias=tuple(float(value) for value in estimator.intercepts_[1].tolist()),
        thresholds=zero_thresholds,
        training_dataset_hash=dataset_hash(args.train_cases, args.oos_cases),
        seed=args.seed,
    )
    classifier = NonlinearRouteClassifier(uncalibrated)
    raw_validation = [
        prediction_record(classifier, record, apply_thresholds=False)
        for record in validation
    ]
    raw_thresholds = calibrate_thresholds(raw_validation)
    thresholds = {
        key: DecisionThreshold(min_confidence=values[0], min_margin=values[1])
        for key, values in raw_thresholds.items()
    }
    calibrated = NonlinearRouteModel(
        version=uncalibrated.version,
        embedding_model=uncalibrated.embedding_model,
        embedding_dimension=uncalibrated.embedding_dimension,
        labels=uncalibrated.labels,
        hidden_weights=uncalibrated.hidden_weights,
        hidden_bias=uncalibrated.hidden_bias,
        output_weights=uncalibrated.output_weights,
        output_bias=uncalibrated.output_bias,
        thresholds=thresholds,
        training_dataset_hash=uncalibrated.training_dataset_hash,
        seed=uncalibrated.seed,
    )
    calibrated_classifier = NonlinearRouteClassifier(calibrated)
    validation_records = [
        prediction_record(calibrated_classifier, record, apply_thresholds=True)
        for record in validation
    ]
    validation_metrics = summarize(validation_records)

    save_nonlinear_route_model(calibrated, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "embedding_model": calibrated.embedding_model,
                "embedding_dimension": calibrated.embedding_dimension,
                "labels": list(calibrated.labels),
                "hidden_dimension": len(calibrated.hidden_bias),
                "thresholds": {
                    key: {
                        "min_confidence": threshold.min_confidence,
                        "min_margin": threshold.min_margin,
                    }
                    for key, threshold in calibrated.thresholds.items()
                },
                "training_dataset_hash": calibrated.training_dataset_hash,
                "seed": calibrated.seed,
                "validation_metrics": validation_metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
