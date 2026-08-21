from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.domain.capabilities import CapabilitySpec
from app.domain.semantics import SchedulingCommand
from app.ports.llm import GenerationConfig, LlmPort
from app.ports.reranker import RerankerPort


class CapabilityJudgeOutput(BaseModel):
    capability_name: str


class CapabilitySelector:
    def __init__(
        self,
        reranker: RerankerPort,
        llm: LlmPort,
        judge_config: GenerationConfig,
        *,
        min_margin: float = 0.08,
    ) -> None:
        self._reranker = reranker
        self._llm = llm
        self._judge_config = judge_config
        self._min_margin = min_margin

    async def select(
        self,
        command: SchedulingCommand,
        facts: frozenset[str],
        candidates: tuple[CapabilitySpec, ...],
    ) -> CapabilitySpec:
        if not candidates:
            raise ValueError("No eligible capability candidates")
        if len(candidates) == 1:
            return candidates[0]

        query = json.dumps(
            {
                "act": command.act.value,
                "start_date": str(command.start_date) if command.start_date else None,
                "end_date": str(command.end_date) if command.end_date else None,
                "slot_id": command.slot_id,
                "facts": sorted(facts),
            },
            ensure_ascii=False,
        )
        try:
            scores = await self._reranker.rerank(query, [item.description for item in candidates])
            ranked = sorted(zip(candidates, scores, strict=True), key=lambda item: item[1], reverse=True)
            if len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= self._min_margin:
                return ranked[0][0]
        except Exception:
            pass

        allowed = {item.name: item.description for item in candidates}
        messages = [
            {
                "role": "system",
                "content": (
                    "Choose exactly one capability_name from CAPABILITIES. The candidates are already safe/applicable "
                    "with respect to known state. Choose the capability that best matches the interpreted visitor act."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"COMMAND": command.model_dump(mode="json"), "FACTS": sorted(facts), "CAPABILITIES": allowed},
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            raw = await self._llm.complete(messages, self._judge_config, response_schema=CapabilityJudgeOutput)
            parsed = CapabilityJudgeOutput.model_validate_json(raw)
            return next(item for item in candidates if item.name == parsed.capability_name)
        except (ValidationError, ValueError, StopIteration, Exception):
            # The registry already reduced the set to applicable capabilities. A stable
            # declaration order is safer than inventing an unavailable action.
            return candidates[0]
