from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.domain.routing import Route
from app.infrastructure.business_route_classifier import (
    BusinessRouteClassifier,
    RouteModel,
    save_route_model,
)
from tests.evals.intent_metrics import calibrate_thresholds


DEFAULT_SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the offline business-route classifier.")
    parser.add_argument("--train-vectors", type=Path, required=True)
    parser.add_argument("--validation-vectors", type=Path, required=True)
    parser.add_argument("--train-cases", type=Path, required=True)
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


def prediction_record(
    classifier: BusinessRouteClassifier,
    record: dict[str, Any],
) -> dict[str, Any]:
    prediction = classifier.predict([float(value) for value in record["embedding"]])
    return {
        "expected_intent": record.get("intent"),
        "predicted_intent": None,
        "expected_route": record.get("route"),
        "predicted_route": prediction.route.value,
        "accepted": True,
        "critical": bool(record.get("critical", False)),
        "confidence": prediction.confidence,
        "margin": prediction.margin,
        "latency_ms": 0.0,
        "source": "route_classifier",
    }


def main() -> int:
    args = parse_args()
    train_embedding_model, train = load_vectors(args.train_vectors)
    validation_embedding_model, validation = load_vectors(args.validation_vectors)
    if train_embedding_model != validation_embedding_model:
        raise ValueError("train and validation embeddings use different models")
    if any(record.get("route") is None for record in train):
        raise ValueError("out-of-scope examples must not be used as a trained route")

    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required only for offline training; "
            "run this script with `uv run --with scikit-learn`"
        ) from exc

    x_train = [[float(value) for value in record["embedding"]] for record in train]
    y_train = [str(record["route"]) for record in train]
    dimension = len(x_train[0])

    estimator = LogisticRegression(
        solver="lbfgs",
        max_iter=2000,
        class_weight="balanced",
        random_state=args.seed,
    )
    estimator.fit(x_train, y_train)

    routes = tuple(Route(value) for value in estimator.classes_)
    if set(routes) != set(Route):
        missing = sorted(route.value for route in set(Route) - set(routes))
        raise ValueError(f"training data is missing routes: {missing}")

    uncalibrated = RouteModel(
        version=2,
        embedding_model=train_embedding_model,
        embedding_dimension=dimension,
        routes=routes,
        coefficients=tuple(
            tuple(float(value) for value in row)
            for row in estimator.coef_.tolist()
        ),
        intercepts=tuple(float(value) for value in estimator.intercept_.tolist()),
        min_confidence=0.0,
        min_margin=0.0,
        training_dataset_hash=hashlib.sha256(
            args.train_cases.read_bytes()
        ).hexdigest(),
        seed=args.seed,
    )
    classifier = BusinessRouteClassifier(uncalibrated)
    validation_records = [
        prediction_record(classifier, record)
        for record in validation
    ]
    min_confidence, min_margin = calibrate_thresholds(validation_records)

    calibrated = RouteModel(
        version=uncalibrated.version,
        embedding_model=uncalibrated.embedding_model,
        embedding_dimension=uncalibrated.embedding_dimension,
        routes=uncalibrated.routes,
        coefficients=uncalibrated.coefficients,
        intercepts=uncalibrated.intercepts,
        min_confidence=min_confidence,
        min_margin=min_margin,
        training_dataset_hash=uncalibrated.training_dataset_hash,
        seed=uncalibrated.seed,
    )
    save_route_model(calibrated, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "embedding_model": calibrated.embedding_model,
                "embedding_dimension": calibrated.embedding_dimension,
                "routes": [route.value for route in calibrated.routes],
                "min_confidence": calibrated.min_confidence,
                "min_margin": calibrated.min_margin,
                "training_dataset_hash": calibrated.training_dataset_hash,
                "seed": calibrated.seed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
