from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.ports.llm import GenerationConfig, LlmPort
from app.ports.reranker import RerankerPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteSpec:
    key: str
    domain: RouteDomain
    relation: RouteRelation
    description: str


class RoutingJudgeOutput(BaseModel):
    route_key: str


_NO_WORKFLOW_ROUTES = (
    RouteSpec(
        "business_new",
        RouteDomain.BUSINESS,
        RouteRelation.NEW,
        "The visitor is asking about Diego's professional work, experience, projects, technologies, services, rates, clients, credentials, background, or capabilities.",
    ),
    RouteSpec(
        "scheduling_new",
        RouteDomain.SCHEDULING,
        RouteRelation.NEW,
        "The visitor wants to start arranging a meeting, call, appointment, availability search, or calendar interaction with Diego.",
    ),
    RouteSpec(
        "general_new",
        RouteDomain.GENERAL,
        RouteRelation.NEW,
        "The visitor is making general conversation or asking something unrelated to Diego's professional work and unrelated to arranging a meeting.",
    ),
)

_ACTIVE_SCHEDULING_ROUTES = (
    RouteSpec(
        "business_interrupt",
        RouteDomain.BUSINESS,
        RouteRelation.INTERRUPT,
        "The visitor is temporarily switching away from an active scheduling workflow to ask about Diego's professional work, experience, projects, technologies, services, rates, clients, credentials, background, or capabilities. The scheduling workflow should be preserved.",
    ),
    RouteSpec(
        "scheduling_continue",
        RouteDomain.SCHEDULING,
        RouteRelation.CONTINUE,
        "The visitor is continuing, resuming, changing, cancelling, or providing details for the active scheduling workflow, including selecting a previously offered slot or date.",
    ),
    RouteSpec(
        "general_interrupt",
        RouteDomain.GENERAL,
        RouteRelation.INTERRUPT,
        "The visitor is temporarily switching away from an active scheduling workflow for general conversation unrelated to Diego's professional work and unrelated to scheduling. The scheduling workflow should be preserved.",
    ),
)


class CascadingSemanticRouter:
    def __init__(
        self,
        reranker: RerankerPort,
        llm: LlmPort,
        judge_config: GenerationConfig,
        *,
        min_score: float = 0.10,
        min_margin: float = 0.08,
    ) -> None:
        self._reranker = reranker
        self._llm = llm
        self._judge_config = judge_config
        self._min_score = min_score
        self._min_margin = min_margin

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        candidates = self._candidates(state)
        query = self._query(state, user_message)
        scores: list[float] = []

        try:
            scores = await self._reranker.rerank(
                query,
                [candidate.description for candidate in candidates],
            )
        except Exception as exc:
            logger.warning("semantic reranker unavailable: %s", exc)
            return await self._judge(state, query, candidates, {})

        ranked = sorted(
            zip(candidates, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        top_spec, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        score_map = {spec.key: score for spec, score in zip(candidates, scores, strict=True)}
        margin = top_score - second_score

        if top_score < self._min_score or margin < self._min_margin:
            return await self._judge(state, query, candidates, score_map)

        decision = self._decision(top_spec, top_score, "reranker", score_map)
        self._log_decision(state, decision, margin)
        return decision

    async def _judge(
        self,
        state: SessionState,
        query: str,
        candidates: tuple[RouteSpec, ...],
        score_map: dict[str, float],
    ) -> RoutingDecision:
        allowed = {candidate.key: candidate.description for candidate in candidates}
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a routing judge. Select exactly one route_key from the supplied ROUTES. "
                    "Use the current workflow state and the visitor's latest message. Do not answer the visitor."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"CONTEXT": query, "ROUTES": allowed},
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            raw = await self._llm.complete(
                messages,
                self._judge_config,
                response_schema=RoutingJudgeOutput,
            )
            parsed = self._parse_judge(raw)
            spec = next(candidate for candidate in candidates if candidate.key == parsed.route_key)
        except (ValidationError, ValueError, StopIteration, Exception) as exc:
            logger.warning("routing judge failed: %s", exc)
            spec = self._safe_fallback(candidates, score_map)

        confidence = score_map.get(spec.key, 0.5 if not score_map else 0.0)
        decision = self._decision(spec, confidence, "llm_judge", score_map)
        self._log_decision(state, decision, None)
        return decision

    @staticmethod
    def _parse_judge(raw: str) -> RoutingJudgeOutput:
        try:
            return RoutingJudgeOutput.model_validate_json(raw)
        except ValidationError as first_error:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return RoutingJudgeOutput.model_validate_json(raw[start : end + 1])
            raise first_error

    @staticmethod
    def _candidates(state: SessionState) -> tuple[RouteSpec, ...]:
        if state.active_workflow == ActiveWorkflow.SCHEDULING:
            return _ACTIVE_SCHEDULING_ROUTES
        return _NO_WORKFLOW_ROUTES

    @staticmethod
    def _query(state: SessionState, user_message: str) -> str:
        last_assistant = next(
            (turn.content for turn in reversed(state.turns[:-1]) if turn.role == "assistant"),
            "",
        )
        return "\n".join(
            [
                "Classify the latest visitor message for a digital business representative.",
                f"CURRENT_FOCUS: {state.current_focus.value}",
                f"ACTIVE_WORKFLOW: {state.active_workflow.value if state.active_workflow else 'none'}",
                f"WORKFLOW_STAGE: {state.stage.value}",
                f"HAS_OFFERED_SLOTS: {bool(state.offered_slots)}",
                f"HAS_PENDING_BOOKING: {state.pending_booking is not None}",
                f"LAST_ASSISTANT_MESSAGE: {last_assistant}",
                f"VISITOR_MESSAGE: {user_message}",
            ]
        )

    @staticmethod
    def _decision(
        spec: RouteSpec,
        confidence: float,
        source: str,
        scores: dict[str, float],
    ) -> RoutingDecision:
        return RoutingDecision(
            domain=spec.domain,
            relation=spec.relation,
            route_key=spec.key,
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
            scores=scores,
        )

    @staticmethod
    def _safe_fallback(
        candidates: tuple[RouteSpec, ...],
        score_map: dict[str, float],
    ) -> RouteSpec:
        if score_map:
            return max(candidates, key=lambda candidate: score_map.get(candidate.key, 0.0))
        return next(candidate for candidate in candidates if candidate.domain == RouteDomain.GENERAL)

    @staticmethod
    def _log_decision(
        state: SessionState,
        decision: RoutingDecision,
        margin: float | None,
    ) -> None:
        logger.info(
            "route=%s domain=%s relation=%s source=%s confidence=%.4f margin=%s stage=%s workflow=%s",
            decision.route_key,
            decision.domain.value,
            decision.relation.value,
            decision.source,
            decision.confidence,
            f"{margin:.4f}" if margin is not None else "n/a",
            state.stage.value,
            state.active_workflow.value if state.active_workflow else "none",
        )
