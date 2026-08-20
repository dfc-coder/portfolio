from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from app.domain.conversation import SessionState
from app.domain.planning import Observation, Plan
from app.ports.llm import GenerationConfig, LlmPort

from .context import ContextBuilder
from .fsm import ConversationFSM


@dataclass(frozen=True)
class PlanningFailure(Exception):
    message: str
    raw_output: str = ""

    def __str__(self) -> str:
        return self.message


class StructuredPlanner:
    def __init__(
        self,
        llm: LlmPort,
        context: ContextBuilder,
        fsm: ConversationFSM,
        planner_config: GenerationConfig,
        repair_config: GenerationConfig,
    ) -> None:
        self._llm = llm
        self._context = context
        self._fsm = fsm
        self._planner_config = planner_config
        self._repair_config = repair_config

    async def plan(
        self,
        state: SessionState,
        user_message: str,
        observation: Observation | None = None,
    ) -> Plan:
        messages = self._context.planner_messages(
            state,
            user_message,
            self._fsm.allowed_actions(state.stage),
            observation=observation,
        )
        raw = await self._llm.complete(messages, self._planner_config, response_schema=Plan)
        return self._parse(raw)

    async def repair(
        self,
        state: SessionState,
        user_message: str,
        issues: list[str],
        observation: Observation | None = None,
    ) -> Plan:
        messages = self._context.planner_messages(
            state,
            user_message,
            self._fsm.allowed_actions(state.stage),
            observation=observation,
            issues=issues,
        )
        raw = await self._llm.complete(messages, self._repair_config, response_schema=Plan)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> Plan:
        try:
            return Plan.model_validate_json(raw)
        except ValidationError as first_error:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return Plan.model_validate_json(raw[start : end + 1])
                except ValidationError:
                    pass
            raise PlanningFailure("Planner returned invalid structured output.", raw) from first_error
