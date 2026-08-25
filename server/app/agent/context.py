from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain
from app.ports.embeddings import EmbeddingPort

from .similarity import cosine_similarity

if TYPE_CHECKING:
    from app.infrastructure.pockettrace import TurnTrace

logger = logging.getLogger(__name__)


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
    """Flatten structured profile data into small retrievable units."""

    def __init__(self, profile: BusinessProfile) -> None:
        self.documents = tuple(self._build(profile))

    @classmethod
    def _build(cls, profile: BusinessProfile) -> list[ProfileDocument]:
        documents: list[ProfileDocument] = []

        def add(document_id: str, payload: object) -> None:
            documents.append(
                ProfileDocument(
                    document_id=document_id,
                    text=json.dumps(payload, ensure_ascii=False),
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
    """Canonical dense retrieval: precomputed document vectors + cosine top-k."""

    def __init__(
        self,
        index: ProfileDocumentIndex,
        embeddings: EmbeddingPort,
        *,
        max_chars: int = 4000,
        max_documents: int = 4,
    ) -> None:
        self._index = index
        self._embeddings = embeddings
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._document_vectors: list[list[float]] | None = None
        self._index_lock = asyncio.Lock()

    async def warm(self) -> None:
        await self._ensure_index()

    async def search(self, query: str) -> tuple[RetrievedDocument, ...]:
        documents = self._index.documents
        if not documents or not query.strip():
            return ()

        await self._ensure_index()
        assert self._document_vectors is not None
        query_vector = await self._embeddings.embed_query(query)
        ranked = sorted(
            (
                RetrievedDocument(
                    document=document,
                    score=cosine_similarity(query_vector, vector),
                )
                for document, vector in zip(
                    documents,
                    self._document_vectors,
                    strict=True,
                )
            ),
            key=lambda item: item.score,
            reverse=True,
        )

        selected: list[RetrievedDocument] = []
        used_chars = 0
        for item in ranked:
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

    async def _ensure_index(self) -> None:
        if self._document_vectors is not None:
            return
        async with self._index_lock:
            if self._document_vectors is not None:
                return
            vectors = await self._embeddings.embed_documents(
                [document.text for document in self._index.documents]
            )
            if len(vectors) != len(self._index.documents):
                raise ValueError("Embedding service returned an unexpected profile vector count")
            self._document_vectors = vectors


_GENERAL_PROMPT = """You are a website assistant speaking with a visitor.
Reply in the visitor's language. Be concise, natural and useful.
Always answer the most recent visitor message directly. Earlier conversation turns are context only; never answer an older question instead of the latest one.
Do not greet unless the most recent visitor message is itself a greeting. Do not introduce yourself unless the visitor asks who or what you are.
Do not introduce yourself as a named person and do not assign a personal identity to the visitor.
RUNTIME_STATE contains verified facts supplied by the application. Treat those values as authoritative. If the visitor asks for information present in RUNTIME_STATE, answer directly from it and never claim that information is unavailable.
Free-form generated text never executes external actions.
Never claim an external action happened unless verified runtime state explicitly says it did.
Keep normal answers under 120 words unless the visitor asks for detail.
"""

_BUSINESS_PROMPT = """You are the digital business representative for a professional portfolio.
Reply in the visitor's language. Be concise, natural and useful.
Always answer the most recent visitor message directly. Earlier conversation turns are context only; never answer an older question instead of the latest one.
The visitor is an unknown visitor. PORTFOLIO_SUBJECT is the professional being discussed, not you and not the visitor.
Always refer to PORTFOLIO_SUBJECT in the third person. Never introduce yourself as PORTFOLIO_SUBJECT and never address the visitor as PORTFOLIO_SUBJECT unless the visitor explicitly identifies themself that way.
RUNTIME_STATE contains verified facts supplied by the application. Treat those values as authoritative.
For facts about PORTFOLIO_SUBJECT, use only facts explicitly present in RELEVANT_KNOWLEDGE.
Do not infer, guess, embellish or combine facts into unsupported claims.
Absence of a fact is not evidence of the opposite. If relevant knowledge is missing, say that the information is not available.
Do not invent clients, rates, availability, results, credentials or dates.
Free-form generated text never executes a side effect. Calendar creation requires an explicit human approval action in the interface; chat text alone cannot authorize it.
Never claim an external action happened unless verified runtime state explicitly says it did.
Keep normal answers under 120 words unless the visitor asks for detail.
"""


class ContextAssembler:
    """Build route-scoped prompts with only the context needed for that turn."""

    def __init__(
        self,
        profile: BusinessProfile,
        capabilities: tuple[str, ...],
        retriever: ProfileRetriever,
        *,
        history_turns: int = 4,
    ) -> None:
        self._timezone = ZoneInfo(profile.scheduling.timezone)
        self._retriever = retriever
        self._history_turns = max(1, history_turns)

        policy = "\n".join(f"- {item}" for item in profile.instructions)
        capabilities_text = "\n".join(f"- {item}" for item in capabilities)
        self._business_prefix = (
            f"{_BUSINESS_PROMPT}\n"
            f"PORTFOLIO_SUBJECT={profile.owner.name}\n"
            f"TIMEZONE={profile.scheduling.timezone}\n"
            f"AGENT_CAPABILITIES:\n{capabilities_text}\n"
            f"OWNER_POLICY:\n{policy}"
        )

    async def warm(self) -> None:
        await self._retriever.warm()

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
            prefix = self._business_prefix
        else:
            prefix = _GENERAL_PROMPT

        system_prompt = f"{prefix}\n\n" + "\n\n".join(dynamic_parts)
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
