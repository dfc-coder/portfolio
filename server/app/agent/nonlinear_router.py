from __future__ import annotations

from app.agent.router import _has_explicit_scheduling_fields
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import Intent, Route, RoutingDecision
from app.infrastructure.nonlinear_route_classifier import NonlinearRouteClassifier
from app.ports.embeddings import EmbeddingPort, EmbeddingTask


class NonlinearRouteRouter:
    """Four-class supervised router with explicit OOS and scheduling state safety."""

    def __init__(
        self,
        embeddings: EmbeddingPort,
        classifier: NonlinearRouteClassifier,
    ) -> None:
        self._embeddings = embeddings
        self._classifier = classifier

    async def warm(self) -> None:
        return None

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        if (
            state.active_workflow == ActiveWorkflow.SCHEDULING
            and _has_explicit_scheduling_fields(user_message)
        ):
            return RoutingDecision(
                domain=Route.SCHEDULING,
                intent=Intent.SCHEDULE_CONTINUE,
                route_key="scheduling_explicit",
                confidence=1.0,
                margin=1.0,
                source="deterministic_scheduling",
                scores={Route.SCHEDULING.value: 1.0},
            )

        embedding = await self._embeddings.embed_query(
            user_message,
            EmbeddingTask.ROUTING,
        )
        prediction = self._classifier.predict(embedding)
        active_scheduling = state.active_workflow == ActiveWorkflow.SCHEDULING
        accepted = self._classifier.accepts(
            prediction,
            active_scheduling=active_scheduling,
        )

        if prediction.route is None:
            return RoutingDecision(
                domain=None,
                intent=None,
                accepted=False,
                route_key="oos",
                confidence=prediction.confidence,
                margin=prediction.margin,
                source="oos_classifier",
                scores=prediction.scores,
            )

        return RoutingDecision(
            domain=prediction.route if accepted else None,
            intent=None,
            accepted=accepted,
            route_key=prediction.route.value if accepted else "abstain",
            confidence=prediction.confidence,
            margin=prediction.margin,
            source="nonlinear_route_classifier" if accepted else "abstain",
            scores=prediction.scores,
        )
