from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.domain.routing import Route


@dataclass(frozen=True)
class RoutePrediction:
    route: Route
    confidence: float
    second_route: Route | None
    margin: float
    scores: dict[str, float]


@dataclass(frozen=True)
class SchedulingBoundaryPrediction:
    is_capability: bool
    confidence: float
    margin: float
    scores: dict[str, float]


@dataclass(frozen=True)
class RouteThreshold:
    min_confidence: float
    min_margin: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.0 <= self.min_margin <= 1.0:
            raise ValueError("min_margin must be between 0 and 1")


_REQUIRED_THRESHOLD_KEYS = {
    Route.CONVERSATION.value,
    Route.PORTFOLIO.value,
    Route.SCHEDULING.value,
    "scheduling_active",
}


@dataclass(frozen=True)
class RouteModel:
    version: int
    embedding_model: str
    embedding_dimension: int
    routes: tuple[Route, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    thresholds: dict[str, RouteThreshold]
    scheduling_boundary_coefficients: tuple[float, ...]
    scheduling_boundary_intercept: float
    scheduling_boundary_threshold: RouteThreshold
    training_dataset_hash: str
    seed: int

    def __post_init__(self) -> None:
        if self.version < 4:
            raise ValueError("route model version must be >= 4")
        if self.embedding_dimension < 1:
            raise ValueError("embedding dimension must be >= 1")
        if len(self.routes) < 2:
            raise ValueError("route model requires at least two routes")
        if len(set(self.routes)) != len(self.routes):
            raise ValueError("route model contains duplicate routes")
        if len(self.coefficients) != len(self.routes):
            raise ValueError("coefficient row count must match route count")
        if len(self.intercepts) != len(self.routes):
            raise ValueError("intercept count must match route count")
        if any(len(row) != self.embedding_dimension for row in self.coefficients):
            raise ValueError("coefficient dimension does not match embedding dimension")
        if len(self.scheduling_boundary_coefficients) != self.embedding_dimension:
            raise ValueError("scheduling boundary dimension does not match embedding dimension")
        if set(self.thresholds) != _REQUIRED_THRESHOLD_KEYS:
            raise ValueError(
                "route thresholds must define conversation, portfolio, scheduling, "
                "and scheduling_active"
            )
        if not self.embedding_model.strip():
            raise ValueError("embedding_model is required")
        if not self.training_dataset_hash.strip():
            raise ValueError("training_dataset_hash is required")

    def threshold_for(
        self,
        route: Route,
        *,
        active_scheduling: bool,
    ) -> RouteThreshold:
        key = (
            "scheduling_active"
            if route == Route.SCHEDULING and active_scheduling
            else route.value
        )
        return self.thresholds[key]


class BusinessRouteClassifier:
    """Two small linear heads over the same frozen routing embedding."""

    def __init__(self, model: RouteModel) -> None:
        self.model = model

    def predict(self, embedding: list[float]) -> RoutePrediction:
        self._validate_embedding(embedding)
        logits = [
            sum(weight * value for weight, value in zip(row, embedding, strict=True))
            + intercept
            for row, intercept in zip(
                self.model.coefficients,
                self.model.intercepts,
                strict=True,
            )
        ]
        probabilities = _softmax(logits)
        ranked = sorted(
            range(len(probabilities)),
            key=probabilities.__getitem__,
            reverse=True,
        )
        best_index = ranked[0]
        second_index = ranked[1] if len(ranked) > 1 else None
        confidence = probabilities[best_index]
        second_score = probabilities[second_index] if second_index is not None else 0.0

        return RoutePrediction(
            route=self.model.routes[best_index],
            confidence=confidence,
            second_route=(
                self.model.routes[second_index]
                if second_index is not None
                else None
            ),
            margin=confidence - second_score,
            scores={
                route.value: score
                for route, score in zip(
                    self.model.routes,
                    probabilities,
                    strict=True,
                )
            },
        )

    def predict_scheduling_boundary(
        self,
        embedding: list[float],
    ) -> SchedulingBoundaryPrediction:
        """Distinguish a scheduling capability question from an actual scheduling action."""
        self._validate_embedding(embedding)
        action_logit = (
            sum(
                weight * value
                for weight, value in zip(
                    self.model.scheduling_boundary_coefficients,
                    embedding,
                    strict=True,
                )
            )
            + self.model.scheduling_boundary_intercept
        )
        action_probability = _sigmoid(action_logit)
        capability_probability = 1.0 - action_probability
        is_capability = capability_probability >= action_probability
        confidence = max(capability_probability, action_probability)
        margin = abs(capability_probability - action_probability)
        return SchedulingBoundaryPrediction(
            is_capability=is_capability,
            confidence=confidence,
            margin=margin,
            scores={
                "capability": capability_probability,
                "scheduling_action": action_probability,
            },
        )

    def accepts(
        self,
        prediction: RoutePrediction,
        *,
        active_scheduling: bool,
    ) -> bool:
        threshold = self.model.threshold_for(
            prediction.route,
            active_scheduling=active_scheduling,
        )
        return (
            prediction.confidence >= threshold.min_confidence
            and prediction.margin >= threshold.min_margin
        )

    def accepts_capability_override(
        self,
        prediction: SchedulingBoundaryPrediction,
    ) -> bool:
        threshold = self.model.scheduling_boundary_threshold
        return (
            prediction.is_capability
            and prediction.confidence >= threshold.min_confidence
            and prediction.margin >= threshold.min_margin
        )

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self.model.embedding_dimension:
            raise ValueError(
                "embedding dimension mismatch: "
                f"expected {self.model.embedding_dimension}, got {len(embedding)}"
            )


def load_route_model(path: Path) -> RouteModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        thresholds = {
            str(key): RouteThreshold(
                min_confidence=float(value["min_confidence"]),
                min_margin=float(value["min_margin"]),
            )
            for key, value in payload["thresholds"].items()
        }
        boundary_threshold_payload = payload["scheduling_boundary_threshold"]
        return RouteModel(
            version=int(payload["version"]),
            embedding_model=str(payload["embedding_model"]),
            embedding_dimension=int(payload["embedding_dimension"]),
            routes=tuple(Route(value) for value in payload["routes"]),
            coefficients=tuple(
                tuple(float(value) for value in row)
                for row in payload["coefficients"]
            ),
            intercepts=tuple(float(value) for value in payload["intercepts"]),
            thresholds=thresholds,
            scheduling_boundary_coefficients=tuple(
                float(value) for value in payload["scheduling_boundary_coefficients"]
            ),
            scheduling_boundary_intercept=float(payload["scheduling_boundary_intercept"]),
            scheduling_boundary_threshold=RouteThreshold(
                min_confidence=float(boundary_threshold_payload["min_confidence"]),
                min_margin=float(boundary_threshold_payload["min_margin"]),
            ),
            training_dataset_hash=str(payload["training_dataset_hash"]),
            seed=int(payload["seed"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid route model artifact: {exc}") from exc


def save_route_model(model: RouteModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": model.version,
        "embedding_model": model.embedding_model,
        "embedding_dimension": model.embedding_dimension,
        "routes": [route.value for route in model.routes],
        "coefficients": [list(row) for row in model.coefficients],
        "intercepts": list(model.intercepts),
        "thresholds": {
            key: {
                "min_confidence": threshold.min_confidence,
                "min_margin": threshold.min_margin,
            }
            for key, threshold in model.thresholds.items()
        },
        "scheduling_boundary_coefficients": list(
            model.scheduling_boundary_coefficients
        ),
        "scheduling_boundary_intercept": model.scheduling_boundary_intercept,
        "scheduling_boundary_threshold": {
            "min_confidence": model.scheduling_boundary_threshold.min_confidence,
            "min_margin": model.scheduling_boundary_threshold.min_margin,
        },
        "training_dataset_hash": model.training_dataset_hash,
        "seed": model.seed,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _softmax(logits: list[float]) -> list[float]:
    if not logits:
        raise ValueError("cannot classify without logits")
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)
