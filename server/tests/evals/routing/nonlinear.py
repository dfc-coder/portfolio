from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.agent.router import _has_explicit_scheduling_fields
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import Intent, Route, RoutingDecision
from app.ports.embeddings import EmbeddingPort, EmbeddingTask

OOS_LABEL = "oos"
_REQUIRED_LABELS = {Route.CONVERSATION.value, Route.PORTFOLIO.value, Route.SCHEDULING.value, OOS_LABEL}
_REQUIRED_THRESHOLD_KEYS = {Route.CONVERSATION.value, Route.PORTFOLIO.value, Route.SCHEDULING.value, "scheduling_active"}


@dataclass(frozen=True)
class DecisionThreshold:
    min_confidence: float
    min_margin: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.0 <= self.min_margin <= 1.0:
            raise ValueError("min_margin must be between 0 and 1")


@dataclass(frozen=True)
class NonlinearRoutePrediction:
    label: str
    route: Route | None
    confidence: float
    margin: float
    scores: dict[str, float]


@dataclass(frozen=True)
class NonlinearRouteModel:
    version: int
    embedding_model: str
    embedding_dimension: int
    labels: tuple[str, ...]
    hidden_weights: tuple[tuple[float, ...], ...]
    hidden_bias: tuple[float, ...]
    output_weights: tuple[tuple[float, ...], ...]
    output_bias: tuple[float, ...]
    thresholds: dict[str, DecisionThreshold]
    training_dataset_hash: str
    seed: int

    def __post_init__(self) -> None:
        if self.version < 5:
            raise ValueError("nonlinear route model version must be >= 5")
        if self.embedding_dimension < 1:
            raise ValueError("embedding dimension must be >= 1")
        if set(self.labels) != _REQUIRED_LABELS:
            raise ValueError("nonlinear route model must define conversation, portfolio, scheduling and oos")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("nonlinear route model contains duplicate labels")
        if len(self.hidden_weights) != self.embedding_dimension:
            raise ValueError("hidden input dimension does not match embedding dimension")
        hidden_dimension = len(self.hidden_bias)
        if hidden_dimension < 1:
            raise ValueError("hidden layer must not be empty")
        if any(len(row) != hidden_dimension for row in self.hidden_weights):
            raise ValueError("hidden weight width does not match hidden bias dimension")
        if len(self.output_weights) != hidden_dimension:
            raise ValueError("output input dimension does not match hidden dimension")
        if any(len(row) != len(self.labels) for row in self.output_weights):
            raise ValueError("output weight width does not match label count")
        if len(self.output_bias) != len(self.labels):
            raise ValueError("output bias count does not match label count")
        if set(self.thresholds) != _REQUIRED_THRESHOLD_KEYS:
            raise ValueError("nonlinear route thresholds must define conversation, portfolio, scheduling and scheduling_active")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model is required")
        if not self.training_dataset_hash.strip():
            raise ValueError("training_dataset_hash is required")

    def threshold_for(self, route: Route, *, active_scheduling: bool) -> DecisionThreshold:
        key = "scheduling_active" if route == Route.SCHEDULING and active_scheduling else route.value
        return self.thresholds[key]


class NonlinearRouteClassifier:
    """Evaluation candidate: small tanh MLP over the frozen routing embedding."""

    def __init__(self, model: NonlinearRouteModel) -> None:
        self.model = model

    def predict(self, embedding: list[float]) -> NonlinearRoutePrediction:
        if len(embedding) != self.model.embedding_dimension:
            raise ValueError(f"embedding dimension mismatch: expected {self.model.embedding_dimension}, got {len(embedding)}")
        hidden = [math.tanh(sum(embedding[index] * self.model.hidden_weights[index][hidden_index] for index in range(self.model.embedding_dimension)) + self.model.hidden_bias[hidden_index]) for hidden_index in range(len(self.model.hidden_bias))]
        logits = [sum(hidden[hidden_index] * self.model.output_weights[hidden_index][label_index] for hidden_index in range(len(hidden))) + self.model.output_bias[label_index] for label_index in range(len(self.model.labels))]
        probabilities = _softmax(logits)
        ranked = sorted(range(len(probabilities)), key=probabilities.__getitem__, reverse=True)
        best_index, second_index = ranked[0], ranked[1]
        label = self.model.labels[best_index]
        confidence = probabilities[best_index]
        route = None if label == OOS_LABEL else Route(label)
        return NonlinearRoutePrediction(label=label, route=route, confidence=confidence, margin=confidence - probabilities[second_index], scores={candidate: score for candidate, score in zip(self.model.labels, probabilities, strict=True)})

    def accepts(self, prediction: NonlinearRoutePrediction, *, active_scheduling: bool) -> bool:
        if prediction.route is None:
            return False
        threshold = self.model.threshold_for(prediction.route, active_scheduling=active_scheduling)
        return prediction.confidence >= threshold.min_confidence and prediction.margin >= threshold.min_margin


class NonlinearRouteRouter:
    """Evaluation candidate router with explicit OOS and scheduling-state safety."""

    def __init__(self, embeddings: EmbeddingPort, classifier: NonlinearRouteClassifier) -> None:
        self._embeddings = embeddings
        self._classifier = classifier

    async def warm(self) -> None:
        return None

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        if state.active_workflow == ActiveWorkflow.SCHEDULING and _has_explicit_scheduling_fields(user_message):
            return RoutingDecision(domain=Route.SCHEDULING, intent=Intent.SCHEDULE_CONTINUE, route_key="scheduling_explicit", confidence=1.0, margin=1.0, source="deterministic_scheduling", scores={Route.SCHEDULING.value: 1.0})
        embedding = await self._embeddings.embed_query(user_message, EmbeddingTask.ROUTING)
        prediction = self._classifier.predict(embedding)
        accepted = self._classifier.accepts(prediction, active_scheduling=state.active_workflow == ActiveWorkflow.SCHEDULING)
        if prediction.route is None:
            return RoutingDecision(domain=None, intent=None, accepted=False, route_key="oos", confidence=prediction.confidence, margin=prediction.margin, source="oos_classifier", scores=prediction.scores)
        return RoutingDecision(domain=prediction.route if accepted else None, intent=None, accepted=accepted, route_key=prediction.route.value if accepted else "abstain", confidence=prediction.confidence, margin=prediction.margin, source="nonlinear_route_classifier" if accepted else "abstain", scores=prediction.scores)


def load_nonlinear_route_model(path: Path) -> NonlinearRouteModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        thresholds = {str(key): DecisionThreshold(min_confidence=float(value["min_confidence"]), min_margin=float(value["min_margin"])) for key, value in payload["thresholds"].items()}
        return NonlinearRouteModel(version=int(payload["version"]), embedding_model=str(payload["embedding_model"]), embedding_dimension=int(payload["embedding_dimension"]), labels=tuple(str(value) for value in payload["labels"]), hidden_weights=tuple(tuple(float(value) for value in row) for row in payload["hidden_weights"]), hidden_bias=tuple(float(value) for value in payload["hidden_bias"]), output_weights=tuple(tuple(float(value) for value in row) for row in payload["output_weights"]), output_bias=tuple(float(value) for value in payload["output_bias"]), thresholds=thresholds, training_dataset_hash=str(payload["training_dataset_hash"]), seed=int(payload["seed"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid nonlinear route model artifact: {exc}") from exc


def save_nonlinear_route_model(model: NonlinearRouteModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": model.version, "embedding_model": model.embedding_model, "embedding_dimension": model.embedding_dimension, "labels": list(model.labels), "hidden_weights": [list(row) for row in model.hidden_weights], "hidden_bias": list(model.hidden_bias), "output_weights": [list(row) for row in model.output_weights], "output_bias": list(model.output_bias), "thresholds": {key: {"min_confidence": threshold.min_confidence, "min_margin": threshold.min_margin} for key, threshold in model.thresholds.items()}, "training_dataset_hash": model.training_dataset_hash, "seed": model.seed}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _softmax(logits: list[float]) -> list[float]:
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    total = sum(exponentials)
    return [value / total for value in exponentials]
