from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.domain.conversation import SessionState
from app.domain.planning import AgentAction, Observation
from app.domain.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy

from .prompts.planner import PLANNER_SYSTEM_PROMPT, REPAIR_SYSTEM_PROMPT
from .prompts.renderer import BUSINESS_RENDERER_SYSTEM_PROMPT, BUSINESS_REPAIR_SYSTEM_PROMPT


class ContextBuilder:
    def __init__(self, profile: BusinessProfile, policy: SchedulingPolicy) -> None:
        self._profile = profile
        self._policy = policy

    def planner_messages(
        self,
        state: SessionState,
        user_message: str,
        allowed_actions: frozenset[AgentAction],
        observation: Observation | None = None,
        issues: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        system = REPAIR_SYSTEM_PROMPT if issues else PLANNER_SYSTEM_PROMPT
        state_payload = {
            "stage": state.stage,
            "requested_start_date": state.requested_start_date,
            "requested_end_date": state.requested_end_date,
            "selected_slot_id": state.selected_slot_id,
            "visitor_name": state.visitor_name,
            "visitor_email": state.visitor_email,
            "subject": state.subject,
            "offered_slots": {
                slot_id: {
                    "start": slot.start.isoformat(),
                    "end": slot.end.isoformat(),
                }
                for slot_id, slot in state.offered_slots.items()
            },
        }
        content = {
            "CURRENT_TIME": now.isoformat(),
            "TIMEZONE": self._profile.scheduling.timezone,
            "ALLOWED_ACTIONS": sorted(action.value for action in allowed_actions),
            "STATE": state_payload,
            "OBSERVATION": observation.model_dump(mode="json") if observation else None,
            "VALIDATION_ISSUES": issues or [],
            "RECENT_TURNS": [
                {"role": turn.role, "content": turn.content}
                for turn in state.turns[-4:]
            ],
            "VISITOR_MESSAGE": user_message,
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(content, ensure_ascii=False, default=str)},
        ]

    def business_messages(self, state: SessionState) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        system = (
            f"{BUSINESS_RENDERER_SYSTEM_PROMPT}\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"TIMEZONE={self._profile.scheduling.timezone}\n"
            f"BUSINESS_CONTEXT={self._profile.prompt_context()}"
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(
            {"role": turn.role, "content": turn.content}
            for turn in state.turns[-4:]
        )
        return messages

    def business_repair_messages(
        self,
        state: SessionState,
        candidate: str,
        issues: list[str],
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": (
                    f"{BUSINESS_REPAIR_SYSTEM_PROMPT}\n"
                    f"BUSINESS_CONTEXT={self._profile.prompt_context()}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "VISITOR_MESSAGE": state.turns[-1].content if state.turns else "",
                        "CANDIDATE": candidate,
                        "ISSUES": issues,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
