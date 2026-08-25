from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.ports.reranker import RerankerPort

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace

logger = logging.getLogger(__name__)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class ProfileDocument:
    document_id: str
    text: str


@dataclass(frozen=True)
class RetrievedDocument:
    document: ProfileDocument
    score: float


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


class ProfileDocumentIndex:
    """Flatten structured profile data into retrieval documents without semantic tags."""

    def __init__(self, profile: BusinessProfile) -> None:
        self.documents = tuple(self._build(profile))

    @classmethod
    def _build(cls, profile: BusinessProfile) -> list[ProfileDocument]:
        documents: list[ProfileDocument] = []

        def add(document_id: str, payload: object) -> None:
            documents.append(
                ProfileDocument(
                    document_id=document_id,
                    text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                )
            )

        add("owner", {"owner": profile.owner.model_dump()})
        add("positioning", {"positioning": profile.positioning.model_dump()})

        for index, item in enumerate(profile.experience):
            add(f"experience.{index}", {"experience": item.model_dump()})
        for index, item in enumerate(profile.professional_experience):
            add(
                f"professional_experience.{index}",
                {"professional_experience": item.model_dump()},
            )

        add("skills", {"skills": profile.skills.model_dump()})

        for index, item in enumerate(profile.services):
            add(f"services.{index}", {"service": item.model_dump()})
        for index, item in enumerate(profile.projects):
            add(f"projects.{index}", {"project": item.model_dump()})
        for index, item in enumerate(profile.education):
            add(f"education.{index}", {"education": item.model_dump()})
        for index, item in enumerate(profile.certifications):
            add(f"certifications.{index}", {"certification": item.model_dump()})
        for index, item in enumerate(profile.languages):
            add(f"languages.{index}", {"language": item.model_dump()})

        add("business", {"business": profile.business.model_dump()})
        for index, item in enumerate(profile.faq):
            add(f"faq.{index}", {"faq": item.model_dump()})

        return documents


class ProfileRetriever:
    """Semantic retrieval over the in-memory profile index with a generic lexical fallback."""

    def __init__(
        self,
        index: ProfileDocumentIndex,
        reranker: RerankerPort | None,
        *,
        min_score: float = 0.10,
        max_chars: int = 6000,
        max_documents: int = 6,
    ) -> None:
        self._index = index
        self._reranker = reranker
        self._min_score = min_score
        self._max_chars = max_chars
        self._max_documents = max_documents

    async def search(self, query: str) -> tuple[RetrievedDocument, ...]:
        documents = self._index.documents
        if not documents or not query.strip():
            return ()

        try:
            if self._reranker is None:
                raise RuntimeError("No semantic reranker configured")
            scores = await self._reranker.rerank(
                query,
                [document.text for document in documents],
            )
            if len(scores) != len(documents):
                raise ValueError("Reranker score count does not match profile documents")
            ranked = sorted(
                (
                    RetrievedDocument(document=document, score=float(score))
                    for document, score in zip(documents, scores, strict=True)
                ),
                key=lambda item: item.score,
                reverse=True,
            )
            candidates = [item for item in ranked if item.score >= self._min_score]
        except Exception as exc:  # noqa: BLE001 - retrieval must degrade safely
            logger.warning("profile reranker unavailable; using lexical fallback: %s", exc)
            candidates = self._lexical_candidates(query, documents)

        selected: list[RetrievedDocument] = []
        used_chars = 0
        for item in candidates:
            if len(selected) >= self._max_documents:
                break
            size = len(item.document.text)
            if selected and used_chars + size > self._max_chars:
                continue
            if not selected and size > self._max_chars:
                continue
            selected.append(item)
            used_chars += size
            if used_chars >= self._max_chars:
                break
        return tuple(selected)

    @staticmethod
    def _lexical_candidates(
        query: str,
        documents: tuple[ProfileDocument, ...],
    ) -> list[RetrievedDocument]:
        query_terms = {token.casefold() for token in _WORD_RE.findall(query)}
        if not query_terms:
            return []

        ranked: list[RetrievedDocument] = []
        for document in documents:
            document_terms = {
                token.casefold() for token in _WORD_RE.findall(document.text)
            }
            overlap = len(query_terms & document_terms)
            if overlap:
                ranked.append(
                    RetrievedDocument(
                        document=document,
                        score=overlap / len(query_terms),
                    )
                )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked


_CORE_PROMPT = """You are the conversational business representative for the portfolio owner.
Reply in the visitor's language. Be concise, natural and useful.
You are not the portfolio owner and must never claim to be him or claim to be human.
For an ordinary greeting, greet the visitor naturally and offer help.
Free-form generated text never executes a side effect. Calendar creation requires an explicit human approval action in the interface; chat text alone cannot authorize it.
Never claim an external action happened unless verified runtime state explicitly says it did.
For owner-specific facts, use only facts explicitly present in RELEVANT_KNOWLEDGE.
Do not infer, guess, embellish or combine facts into unsupported claims.
Absence of a fact is not evidence of the opposite. If relevant knowledge is missing, say that the information is not available.
Do not invent clients, rates, availability, results, credentials or dates.
Keep normal answers under 120 words unless the visitor asks for detail.
"""


class ContextAssembler:
    """Build the smallest useful prompt from stable policy, runtime state and retrieved facts."""

    def __init__(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
        retriever: ProfileRetriever,
        *,
        history_turns: int = 4,
    ) -> None:
        self._profile = profile
        self._timezone = ZoneInfo(profile.scheduling.timezone)
        self._retriever = retriever
        self._history_turns = max(1, history_turns)
        policy = "\n".join(f"- {item}" for item in profile.instructions)
        capabilities_text = "\n".join(f"- {item}" for item in capabilities)
        self._stable_prefix = (
            f"{_CORE_PROMPT}\n"
            f"PORTFOLIO_OWNER={profile.owner.name}\n"
            f"REPRESENTATIVE_DISCLOSURE={profile.representative.disclosure}\n"
            f"TIMEZONE={profile.scheduling.timezone}\n"
            f"AGENT_CAPABILITIES:\n{capabilities_text}\n"
            f"OWNER_POLICY:\n{policy}"
        )

    async def build(
        self,
        state: SessionState,
        trace: TurnTrace | None = None,
    ) -> AgentContext:
        started = time.perf_counter()
        retrieved: tuple[RetrievedDocument, ...] = ()
        if state.current_focus == RouteDomain.BUSINESS:
            query = self._retrieval_query(state)
            retrieval_started = time.perf_counter()
            retrieved = await self._retriever.search(query)
            if trace is not None:
                trace.add_span(
                    "profile_retrieval",
                    (time.perf_counter() - retrieval_started) * 1000,
                    input={"query": query},
                    output={
                        "documents": [
                            {
                                "id": item.document.document_id,
                                "score": round(item.score, 6),
                                "content": item.document.text,
                            }
                            for item in retrieved
                        ]
                    },
                )

        dynamic_parts = [self._runtime_state(state)]
        if state.current_focus == RouteDomain.BUSINESS:
            knowledge = self._render_knowledge(retrieved)
            dynamic_parts.append(f"RELEVANT_KNOWLEDGE:\n{knowledge}")

        system_prompt = f"{self._stable_prefix}\n\n" + "\n\n".join(dynamic_parts)
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
            "RUNTIME_STATE:\n"
            f"CURRENT_TIME={now.isoformat()}\n"
            f"CURRENT_FOCUS={state.current_focus.value}\n"
            f"ACTIVE_WORKFLOW={workflow}\n"
            f"LAST_BOOKING_VERIFIED={bool(state.last_booking_id)}\n"
            f"SCHEDULING_FACTS={scheduling_facts or 'none'}"
        )

    @staticmethod
    def _render_knowledge(retrieved: tuple[RetrievedDocument, ...]) -> str:
        if not retrieved:
            return "<none>"
        return "\n".join(
            f"[{item.document.document_id}] {item.document.text}"
            for item in retrieved
        )

    @staticmethod
    def _retrieval_query(state: SessionState) -> str:
        recent = state.turns[-3:]
        return "\n".join(
            f"{turn.role.upper()}: {turn.content}"
            for turn in recent
        )
