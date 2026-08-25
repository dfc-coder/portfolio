from __future__ import annotations

import pytest

from app.agent.context import ContextAssembler, ProfileDocumentIndex, ProfileRetriever
from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain


class RecordingReranker:
    def __init__(self, target: str | None = None) -> None:
        self.target = target
        self.calls: list[tuple[str, list[str]]] = []

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, documents))
        if self.target is None:
            return [0.0 for _ in documents]
        return [0.95 if self.target in document else 0.01 for document in documents]

    async def health(self) -> bool:
        return True


def make_assembler(
    profile: BusinessProfile,
    reranker: RecordingReranker,
) -> ContextAssembler:
    retriever = ProfileRetriever(
        ProfileDocumentIndex(profile),
        reranker,
        min_score=0.10,
        max_chars=6000,
        max_documents=6,
    )
    return ContextAssembler(
        profile,
        ("Answer questions about Diego's professional work.",),
        retriever,
    )


def test_profile_index_is_generated_from_structured_profile(profile: BusinessProfile) -> None:
    index = ProfileDocumentIndex(profile)
    ids = {document.document_id for document in index.documents}

    assert "owner" in ids
    assert "positioning" in ids
    assert "skills" in ids
    assert any(document_id.startswith("projects.") for document_id in ids)
    assert any(document_id.startswith("professional_experience.") for document_id in ids)
    assert all(not hasattr(document, "tags") for document in index.documents)


@pytest.mark.asyncio
async def test_general_context_does_not_retrieve_business_profile(
    profile: BusinessProfile,
) -> None:
    reranker = RecordingReranker(target="PocketTrace")
    assembler = make_assembler(profile, reranker)
    state = SessionState("general-context")
    state.current_focus = RouteDomain.GENERAL
    state.turns.append(ChatTurn(role="user", content="Hola"))

    context = await assembler.build(state)

    assert reranker.calls == []
    assert context.document_ids == ()
    assert "\nRELEVANT_KNOWLEDGE:\n" not in context.system_prompt
    assert context.history[-1].content == "Hola"


@pytest.mark.asyncio
async def test_business_context_contains_only_semantically_selected_documents(
    profile: BusinessProfile,
) -> None:
    # Use a value unique to the PocketTrace project document. "PocketTrace" also
    # appears in an FAQ, which correctly makes that FAQ relevant to a real reranker.
    reranker = RecordingReranker(target="https://github.com/dfc-coder/pockettrace")
    assembler = make_assembler(profile, reranker)
    state = SessionState("business-context")
    state.current_focus = RouteDomain.BUSINESS
    state.turns.append(
        ChatTurn(
            role="user",
            content="¿Qué proyecto de Diego funciona como inspector local de trazas?",
        )
    )

    context = await assembler.build(state)

    assert len(reranker.calls) == 1
    assert len(context.document_ids) == 1
    assert context.document_ids[0].startswith("projects.")
    assert "PocketTrace" in context.system_prompt
    assert "Xarlatan" not in context.system_prompt
    assert "System-G" not in context.system_prompt


@pytest.mark.asyncio
async def test_retrieval_query_keeps_small_recent_context_for_followups(
    profile: BusinessProfile,
) -> None:
    reranker = RecordingReranker(target="Xarlatan")
    assembler = make_assembler(profile, reranker)
    state = SessionState("followup-context")
    state.current_focus = RouteDomain.BUSINESS
    state.turns.extend(
        [
            ChatTurn(role="user", content="Contame sobre Xarlatan"),
            ChatTurn(role="assistant", content="Es un proyecto de voz local-first."),
            ChatTurn(role="user", content="¿Y qué lenguaje usa ahí?"),
        ]
    )

    context = await assembler.build(state)

    query, _documents = reranker.calls[0]
    assert "Contame sobre Xarlatan" in query
    assert "¿Y qué lenguaje usa ahí?" in query
    assert any(document_id.startswith("projects.") for document_id in context.document_ids)
