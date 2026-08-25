from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile

from .knowledge import RetrievedDocument

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentContext:
    system_prompt: str
    history: tuple[ChatTurn, ...]
    document_ids: tuple[str, ...]
    knowledge_chars: int

    def messages(self) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(
            {"role": turn.role, "content": turn.content}
            for turn in self.history
        )
        return messages


_BASE_PROMPT = """You are the assistant embedded in a professional portfolio website.
Reply in the language of the most recent visitor message. Be concise, natural and useful.
Answer the most recent visitor message directly. Earlier conversation turns are context only.
Do not greet unless the most recent visitor message is itself a greeting, and do not introduce yourself unless asked.
RUNTIME_STATE contains verified application facts. Treat them as authoritative and use them directly when relevant.
When PORTFOLIO_KNOWLEDGE is present, it contains the only verified facts you may use about PORTFOLIO_SUBJECT. Refer to PORTFOLIO_SUBJECT in the third person.
When PORTFOLIO_KNOWLEDGE is absent, do not invent facts about the portfolio owner.
Absence of a retrieved fact is not evidence of the opposite.
Free-form chat text never executes external actions. Never claim an external action happened unless RUNTIME_STATE verifies it.
Keep normal answers under 120 words unless the visitor asks for detail.
"""


class ContextAssembler:
    """Assemble one prompt; portfolio knowledge is injected only when retrieval found it."""

    def __init__(
        self,
        profile: BusinessProfile,
        *,
        history_turns: int = 4,
    ) -> None:
        self._owner_name = profile.owner.name
        self._timezone = ZoneInfo(profile.scheduling.timezone)
        self._history_turns = max(1, history_turns)

    async def build(
        self,
        state: SessionState,
        retrieved: tuple[RetrievedDocument, ...],
        trace: TurnTrace | None = None,
    ) -> AgentContext:
        started = time.perf_counter()
        dynamic_parts = [self._runtime_state(state)]

        if retrieved:
            dynamic_parts.append(
                f"PORTFOLIO_SUBJECT={self._owner_name}\n"
                f"PORTFOLIO_KNOWLEDGE:\n{self._render_knowledge(retrieved)}"
            )

        system_prompt = f"{_BASE_PROMPT}\n\n" + "\n\n".join(dynamic_parts)
        history = tuple(state.turns[-self._history_turns :])
        document_ids = tuple(item.document.document_id for item in retrieved)
        knowledge_chars = sum(len(item.document.text) for item in retrieved)

        logger.info(
            "context assembled focus=%s documents=%s knowledge_chars=%s history_turns=%s",
            state.current_focus.value,
            document_ids,
            knowledge_chars,
            len(history),
        )
        if trace is not None:
            trace.add_span(
                "context_assembler",
                (time.perf_counter() - started) * 1000,
                input={
                    "focus": state.current_focus.value,
                    "available_history_turns": len(state.turns),
                },
                output={
                    "selected_documents": list(document_ids),
                    "knowledge_chars": knowledge_chars,
                    "history_turns": len(history),
                },
            )

        return AgentContext(
            system_prompt=system_prompt,
            history=history,
            document_ids=document_ids,
            knowledge_chars=knowledge_chars,
        )

    def _runtime_state(self, state: SessionState) -> str:
        now = datetime.now(timezone.utc).astimezone(self._timezone)
        workflow = state.active_workflow.value if state.active_workflow else "none"
        scheduling_facts = ",".join(sorted(state.scheduling.facts()))
        return (
            "RUNTIME_STATE (verified application facts):\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={workflow}\n"
            f"LAST_BOOKING_VERIFIED={bool(state.last_booking_id)}\n"
            f"SCHEDULING_FACTS={scheduling_facts or 'none'}"
        )

    @staticmethod
    def _render_knowledge(retrieved: tuple[RetrievedDocument, ...]) -> str:
        return "\n".join(
            f"[{item.document.document_id}] {item.document.text}"
            for item in retrieved
        )
