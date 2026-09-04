from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import Route

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace
    from app.portfolio.search import Fact

logger = logging.getLogger(__name__)

CONVERSATION_PROMPT_ID = "conversation-v1"
PORTFOLIO_PROMPT_ID = "portfolio-v1"


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


_CONVERSATION_PROMPT = """You are a website assistant speaking with a visitor.
Reply in the visitor's language. Be concise, natural and useful.
Do not introduce yourself as a named person and do not assign a personal identity to the visitor.
For an ordinary greeting, greet briefly and offer help.
Free-form generated text never executes external actions.
Never claim an external action happened unless verified runtime state explicitly says it did.
Keep normal answers under 120 words unless the visitor asks for detail.
"""

_PORTFOLIO_PROMPT = """You are the digital business representative for a professional portfolio.
Reply in the visitor's language. Be concise, natural and useful.
The visitor is an unknown visitor. PORTFOLIO_SUBJECT is the professional being discussed, not you and not the visitor.
Always refer to PORTFOLIO_SUBJECT in the third person. Never introduce yourself as PORTFOLIO_SUBJECT and never address the visitor as PORTFOLIO_SUBJECT unless the visitor explicitly identifies themself that way.
For facts about PORTFOLIO_SUBJECT, use only facts explicitly present in RELEVANT_KNOWLEDGE.
Do not infer, guess, embellish or combine facts into unsupported claims.
Absence of a fact is not evidence of the opposite. If relevant knowledge is missing, say that the information is not available.
Do not invent clients, rates, availability, results, credentials or dates.
Free-form generated text never executes a side effect. Calendar creation requires an explicit human approval action in the interface; chat text alone cannot authorize it.
Never claim an external action happened unless verified runtime state explicitly says it did.
Keep normal answers under 120 words unless the visitor asks for detail.
"""


def prompt_id_for(route: Route) -> str:
    return PORTFOLIO_PROMPT_ID if route == Route.PORTFOLIO else CONVERSATION_PROMPT_ID


class ContextAssembler:
    """Build response prompts from runtime state and explicit evidence."""

    def __init__(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
        *,
        history_turns: int = 4,
    ) -> None:
        self._timezone = ZoneInfo(profile.scheduling.timezone)
        self._history_turns = max(1, history_turns)

        policy = "\n".join(f"- {item}" for item in profile.instructions)
        capabilities_text = "\n".join(f"- {item}" for item in capabilities)
        self._portfolio_prefix = (
            f"{_PORTFOLIO_PROMPT}\n"
            f"PORTFOLIO_SUBJECT={profile.owner.name}\n"
            f"TIMEZONE={profile.scheduling.timezone}\n"
            f"AGENT_CAPABILITIES:\n{capabilities_text}\n"
            f"OWNER_POLICY:\n{policy}"
        )

    async def warm(self) -> None:
        return None

    async def build(
        self,
        state: SessionState,
        evidence: tuple[Fact, ...] = (),
        trace: TurnTrace | None = None,
    ) -> AgentContext:
        started = time.perf_counter()
        dynamic_parts = [self._runtime_state(state)]
        prompt_id = prompt_id_for(state.current_focus)

        if state.current_focus == Route.PORTFOLIO:
            dynamic_parts.append(
                f"RELEVANT_KNOWLEDGE:\n{self._render_knowledge(evidence)}"
            )
            prefix = self._portfolio_prefix
        else:
            prefix = _CONVERSATION_PROMPT

        system_prompt = f"{prefix}\n\n" + "\n\n".join(dynamic_parts)
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

    def _runtime_state(self, state: SessionState) -> str:
        now = datetime.now(timezone.utc).astimezone(self._timezone)
        workflow = state.active_workflow.value if state.active_workflow else "none"
        scheduling_facts = ",".join(sorted(state.scheduling.facts()))
        return (
            "RUNTIME_STATE:\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={workflow}\n"
            f"LAST_BOOKING_VERIFIED={bool(state.last_booking_id)}\n"
            f"SCHEDULING_FACTS={scheduling_facts or 'none'}"
        )

    @staticmethod
    def _render_knowledge(evidence: tuple[Fact, ...]) -> str:
        if not evidence:
            return "<none>"
        return "\n".join(
            f"[{fact.source}] {fact.text}"
            for fact in evidence
        )
