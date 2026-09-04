from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import Route

from .prompts import (
    CONVERSATION_PROMPT,
    CONVERSATION_PROMPT_ID,
    PORTFOLIO_PROMPT,
    PORTFOLIO_PROMPT_ID,
)

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace
    from app.portfolio.search import Fact

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentContext:
    prompt_id: str
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


class ContextAssembler:
    """Build the current production prompt from runtime state and explicit evidence."""

    def __init__(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
        *,
        history_turns: int = 4,
    ) -> None:
        self._timezone = ZoneInfo(profile.scheduling.timezone)
        self._history_turns = max(1, history_turns)
        self._portfolio_prefix = self._portfolio_context(profile, capabilities)

    def build(
        self,
        state: SessionState,
        evidence: tuple[Fact, ...] = (),
        trace: TurnTrace | None = None,
    ) -> AgentContext:
        started = time.perf_counter()
        runtime_state = self._runtime_state(state)

        if state.current_focus == Route.PORTFOLIO:
            prompt_id = PORTFOLIO_PROMPT_ID
            system_prompt = (
                f"{self._portfolio_prefix}\n\n"
                f"{runtime_state}\n\n"
                f"{self._knowledge(evidence)}"
            )
        else:
            prompt_id = CONVERSATION_PROMPT_ID
            system_prompt = f"{CONVERSATION_PROMPT}\n\n{runtime_state}"

        history = tuple(state.turns[-self._history_turns :])
        document_ids = tuple(fact.source for fact in evidence)
        knowledge_chars = sum(len(fact.text) for fact in evidence)

        logger.info(
            "context assembled prompt=%s focus=%s documents=%s knowledge_chars=%s history_turns=%s",
            prompt_id,
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
                    "prompt_id": prompt_id,
                    "selected_documents": list(document_ids),
                    "knowledge_chars": knowledge_chars,
                    "history_turns": len(history),
                },
            )

        return AgentContext(
            prompt_id=prompt_id,
            system_prompt=system_prompt,
            history=history,
            document_ids=document_ids,
            knowledge_chars=knowledge_chars,
        )

    def _portfolio_context(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
    ) -> str:
        capability_items = "\n".join(
            f"<capability>{self._xml_text(item)}</capability>"
            for item in capabilities
        )
        return (
            f"{PORTFOLIO_PROMPT}\n\n"
            f"<portfolio_subject>\n{self._xml_text(profile.owner.name)}\n</portfolio_subject>\n"
            f"<timezone>\n{self._xml_text(profile.scheduling.timezone)}\n</timezone>\n"
            f"<agent_capabilities>\n{capability_items}\n</agent_capabilities>"
        )

    def _runtime_state(self, state: SessionState) -> str:
        now = datetime.now(timezone.utc).astimezone(self._timezone)
        workflow = state.active_workflow.value if state.active_workflow else "none"
        scheduling_facts = ",".join(sorted(state.scheduling.facts()))
        body = (
            f"CURRENT_TIME={now.isoformat()}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={workflow}\n"
            f"LAST_BOOKING_VERIFIED={bool(state.last_booking_id)}\n"
            f"SCHEDULING_FACTS={scheduling_facts or 'none'}"
        )
        return f"<runtime_state>\n{self._xml_text(body)}\n</runtime_state>"

    def _knowledge(self, evidence: tuple[Fact, ...]) -> str:
        if not evidence:
            return "<relevant_knowledge>\n<none />\n</relevant_knowledge>"
        facts = "\n".join(
            (
                f'<fact source="{escape(fact.source, quote=True)}">'
                f"{self._xml_text(fact.text)}</fact>"
            )
            for fact in evidence
        )
        return f"<relevant_knowledge>\n{facts}\n</relevant_knowledge>"

    @staticmethod
    def _xml_text(value: str) -> str:
        return escape(value, quote=False)
