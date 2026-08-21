from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.domain.conversation import SessionState
from app.domain.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy

from .prompts.renderer import BUSINESS_RENDERER_SYSTEM_PROMPT, BUSINESS_REPAIR_SYSTEM_PROMPT


class ContextBuilder:
    def __init__(self, profile: BusinessProfile, policy: SchedulingPolicy) -> None:
        self._profile = profile
        self._policy = policy

    def business_messages(self, state: SessionState) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        system = (
            f"{BUSINESS_RENDERER_SYSTEM_PROMPT}\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"TIMEZONE={self._profile.scheduling.timezone}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={state.active_workflow.value if state.active_workflow else 'none'}\n"
            f"BUSINESS_CONTEXT={self._profile.prompt_context()}"
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend({"role": turn.role, "content": turn.content} for turn in state.turns[-4:])
        return messages

    def business_repair_messages(self, state: SessionState, candidate: str, issues: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": f"{BUSINESS_REPAIR_SYSTEM_PROMPT}\nBUSINESS_CONTEXT={self._profile.prompt_context()}",
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
