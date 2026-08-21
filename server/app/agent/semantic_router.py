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
    RouteSpec("business_new", RouteDomain.BUSINESS, RouteRelation.NEW, "The visitor is asking about Diego's professional work, experience, projects, technologies, services, rates, clients, credentials, background, capabilities or tools."),
    RouteSpec("scheduling_new", RouteDomain.SCHEDULING, RouteRelation.NEW, "The visitor wants to arrange, reschedule, cancel, search availability for, or otherwise manage a meeting or calendar interaction with Diego."),
    RouteSpec("general_new", RouteDomain.GENERAL, RouteRelation.NEW, "The visitor is making general conversation or asking something unrelated to Diego's professional work and unrelated to arranging a meeting."),
)

_ACTIVE_SCHEDULING_ROUTES = (
    RouteSpec("business_interrupt", RouteDomain.BUSINESS, RouteRelation.INTERRUPT, "The visitor temporarily switches from the active scheduling task to ask about Diego's professional work, technologies, projects, rates, skills, capabilities or tools. Preserve scheduling facts."),
    RouteSpec("scheduling_continue", RouteDomain.SCHEDULING, RouteRelation.CONTINUE, "The visitor continues or resumes the active scheduling task by giving dates/details, selecting a slot, confirming, changing, or cancelling the meeting."),
    RouteSpec("general_interrupt", RouteDomain.GENERAL, RouteRelation.INTERRUPT, "The visitor temporarily switches from active scheduling to unrelated general conversation. Preserve scheduling facts."),
)


class CascadingSemanticRouter:
    def __init__(self, reranker: RerankerPort, llm: LlmPort, judge_config: GenerationConfig, *, min_score: float = 0.10, min_margin: float = 0.08) -> None:
        self._reranker = reranker
        self._llm = llm
        self._judge_config = judge_config
        self._min_score = min_score
        self._min_margin = min_margin

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        return await self._route_candidates(state, user_message, self._candidates(state))

    async def route_non_scheduling(self, state: SessionState, user_message: str) -> RoutingDecision:
        relation = RouteRelation.INTERRUPT if state.active_workflow else RouteRelation.NEW
        candidates = (
            RouteSpec("business_fallback", RouteDomain.BUSINESS, relation, "The visitor asks about Diego's professional work, technologies, projects, rates, skills, capabilities or tools."),
            RouteSpec("general_fallback", RouteDomain.GENERAL, relation, "The visitor is making general conversation unrelated to Diego's professional work."),
        )
        return await self._route_candidates(state, user_message, candidates)

    async def _route_candidates(self, state: SessionState, user_message: str, candidates: tuple[RouteSpec, ...]) -> RoutingDecision:
        query = self._query(state, user_message)
        try:
            scores = await self._reranker.rerank(query, [candidate.description for candidate in candidates])
        except Exception as exc:
            logger.warning("semantic reranker unavailable: %s", exc)
            return await self._judge(state, query, candidates, {})

        ranked = sorted(zip(candidates, scores, strict=True), key=lambda item: item[1], reverse=True)
        top_spec, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        score_map = {spec.key: score for spec, score in zip(candidates, scores, strict=True)}
        margin = top_score - second_score
        if top_score < self._min_score or margin < self._min_margin:
            return await self._judge(state, query, candidates, score_map)
        decision = self._decision(top_spec, top_score, "reranker", score_map)
        self._log_decision(state, decision, margin)
        return decision

    async def _judge(self, state: SessionState, query: str, candidates: tuple[RouteSpec, ...], score_map: dict[str, float]) -> RoutingDecision:
        allowed = {candidate.key: candidate.description for candidate in candidates}
        messages = [
            {"role": "system", "content": "You are a routing judge. Select exactly one route_key from ROUTES using the compact conversation facts and latest visitor message. Do not answer the visitor."},
            {"role": "user", "content": json.dumps({"CONTEXT": query, "ROUTES": allowed}, ensure_ascii=False)},
        ]
        try:
            raw = await self._llm.complete(messages, self._judge_config, response_schema=RoutingJudgeOutput)
            parsed = self._parse_judge(raw)
            spec = next(candidate for candidate in candidates if candidate.key == parsed.route_key)
        except Exception as exc:
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
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                return RoutingJudgeOutput.model_validate_json(raw[start : end + 1])
            raise first_error

    @staticmethod
    def _candidates(state: SessionState) -> tuple[RouteSpec, ...]:
        return _ACTIVE_SCHEDULING_ROUTES if state.active_workflow == ActiveWorkflow.SCHEDULING else _NO_WORKFLOW_ROUTES

    @staticmethod
    def _query(state: SessionState, user_message: str) -> str:
        last_assistant = next((turn.content for turn in reversed(state.turns[:-1]) if turn.role == "assistant"), "")
        memory = state.scheduling
        return "\n".join([
            "Classify the latest visitor message for a digital business representative.",
            f"CURRENT_FOCUS: {state.current_focus.value}",
            f"ACTIVE_WORKFLOW: {state.active_workflow.value if state.active_workflow else 'none'}",
            f"KNOWN_SCHEDULING_FACTS: {','.join(sorted(memory.facts())) or 'none'}",
            f"OFFERED_SLOT_IDS: {','.join(memory.offered_slots) or 'none'}",
            f"LAST_ASSISTANT_MESSAGE: {last_assistant}",
            f"VISITOR_MESSAGE: {user_message}",
        ])

    @staticmethod
    def _decision(spec: RouteSpec, confidence: float, source: str, scores: dict[str, float]) -> RoutingDecision:
        return RoutingDecision(domain=spec.domain, relation=spec.relation, route_key=spec.key, confidence=max(0.0, min(1.0, confidence)), source=source, scores=scores)

    @staticmethod
    def _safe_fallback(candidates: tuple[RouteSpec, ...], score_map: dict[str, float]) -> RouteSpec:
        if score_map:
            return max(candidates, key=lambda candidate: score_map.get(candidate.key, 0.0))
        return next((candidate for candidate in candidates if candidate.domain == RouteDomain.GENERAL), candidates[0])

    @staticmethod
    def _log_decision(state: SessionState, decision: RoutingDecision, margin: float | None) -> None:
        logger.info("route=%s domain=%s relation=%s source=%s confidence=%.4f margin=%s workflow=%s facts=%s", decision.route_key, decision.domain.value, decision.relation.value, decision.source, decision.confidence, f"{margin:.4f}" if margin is not None else "n/a", state.active_workflow.value if state.active_workflow else "none", sorted(state.scheduling.facts()))
