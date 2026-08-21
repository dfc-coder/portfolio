from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from app.domain.conversation import SessionState
from app.domain.routing import RouteRelation
from app.domain.semantics import DialogueAct, SchedulingCommand
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy


class SchedulingInterpreter:
    def __init__(
        self,
        llm: LlmPort,
        policy: SchedulingPolicy,
        config: GenerationConfig,
    ) -> None:
        self._llm = llm
        self._policy = policy
        self._config = config

    async def interpret(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
    ) -> SchedulingCommand:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        memory = state.scheduling
        payload = {
            "CURRENT_TIME": now.isoformat(),
            "TIMEZONE": self._policy.config.timezone,
            "RELATION": relation.value,
            "ACTIVE_WORKFLOW": state.active_workflow.value if state.active_workflow else None,
            "KNOWN": {
                "requested_start_date": memory.requested_start_date,
                "requested_end_date": memory.requested_end_date,
                "offered_slot_ids": list(memory.offered_slots),
                "selected_slot_id": memory.selected_slot_id,
                "has_name": bool(memory.visitor_name),
                "has_email": bool(memory.visitor_email),
                "has_subject": bool(memory.subject),
                "has_pending_booking": memory.pending_booking is not None,
            },
            "VISITOR_MESSAGE": user_message,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Interpret only the latest visitor turn for a scheduling capability system. "
                    "Return structured data only. Do not choose tools. "
                    "Acts: request=asks to arrange/search availability; inform=provides dates or meeting details; "
                    "select=chooses an offered slot; confirm=explicitly confirms a pending booking; "
                    "cancel=cancels the scheduling workflow; not_applicable=the message does not start, continue, "
                    "or manage scheduling. Professional questions about technologies, projects, rates, skills or tools "
                    "are not_applicable even when a scheduling workflow is active. "
                    "Resolve relative dates from CURRENT_TIME. Copy only information actually present in the visitor message."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        try:
            raw = await self._llm.complete(messages, self._config, response_schema=SchedulingCommand)
            return SchedulingCommand.model_validate_json(raw)
        except (ValidationError, ValueError):
            return SchedulingCommand(act=DialogueAct.NOT_APPLICABLE)
