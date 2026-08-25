from __future__ import annotations

import pytest

from app.agent.context import ContextAssembler, ProfileDocumentIndex, ProfileRetriever
from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain


class RecordingEmbeddings:
    def __init__(self, target: str | None = None) -> None:
        self.target = target
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [
            [1.0, 0.0] if self.target and self.target in text else [0.0, 1.0]
            for text in texts
        ]

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [1.0, 0.0]

    async def health(self) -> bool:
        return True


def make_assembler(
    profile: BusinessProfile,
    embeddings: RecordingEmbeddings,
) -> ContextAssembler:
    retriever = ProfileRetriever(
        ProfileDocumentIndex(profile),
        embeddings,
        max_chars=6000,
        max_documents=1,
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
async def test_general_context_does_not_retrieve_or_expose_business_identity(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="PocketTrace")
    assembler = make_assembler(profile, embeddings)
    state = SessionState("general-context")
    state.current_focus = RouteDomain.GENERAL
    state.turns.append(ChatTurn(role="user", content="Hola"))

    context = await assembler.build(state)

    assert embeddings.document_calls == []
    assert embeddings.query_calls == []
    assert context.document_ids == ()
    assert "\nRELEVANT_KNOWLEDGE:\n" not in context.system_prompt
    assert profile.owner.name not in context.system_prompt
    assert profile.representative.disclosure not in context.system_prompt
    assert "PORTFOLIO_SUBJECT=" not in context.system_prompt
    assert "AGENT_CAPABILITIES:" not in context.system_prompt
    assert "OWNER_POLICY:" not in context.system_prompt
    assert "website assistant speaking with a visitor" in context.system_prompt
    assert "Always answer the most recent visitor message directly" in context.system_prompt
    assert "Do not greet unless the most recent visitor message is itself a greeting" in context.system_prompt
    assert "RUNTIME_STATE contains verified facts supplied by the application" in context.system_prompt
    assert "RUNTIME_STATE (verified application facts):" in context.system_prompt
    assert "CURRENT_TIME=" in context.system_prompt
    assert context.history[-1].content == "Hola"


@pytest.mark.asyncio
async def test_latest_visitor_turn_stays_last_when_history_contains_an_old_greeting(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings()
    assembler = make_assembler(profile, embeddings)
    state = SessionState("latest-turn")
    state.current_focus = RouteDomain.GENERAL
    state.turns.extend(
        [
            ChatTurn(role="user", content="Hola"),
            ChatTurn(role="assistant", content="Hola, ¿en qué puedo ayudarte?"),
            ChatTurn(role="user", content="¿Qué hora es?"),
        ]
    )

    context = await assembler.build(state)
    messages = context.messages()

    assert messages[-1] == {"role": "user", "content": "¿Qué hora es?"}
    assert "Earlier conversation turns are context only" in messages[0]["content"]
    assert "never claim that information is unavailable" in messages[0]["content"]


@pytest.mark.asyncio
async def test_business_context_contains_top_dense_retrieval_document(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="https://github.com/dfc-coder/pockettrace")
    assembler = make_assembler(profile, embeddings)
    state = SessionState("business-context")
    state.current_focus = RouteDomain.BUSINESS
    state.turns.append(
        ChatTurn(
            role="user",
            content="¿Qué proyecto de Diego funciona como inspector local de trazas?",
        )
    )

    context = await assembler.build(state)

    assert len(embeddings.document_calls) == 1
    assert len(embeddings.query_calls) == 1
    assert len(context.document_ids) == 1
    assert context.document_ids[0].startswith("projects.")
    assert f"PORTFOLIO_SUBJECT={profile.owner.name}" in context.system_prompt
    assert "PORTFOLIO_SUBJECT is the professional being discussed, not you and not the visitor" in context.system_prompt
    assert "Always answer the most recent visitor message directly" in context.system_prompt
    assert "PocketTrace" in context.system_prompt
    assert "Xarlatan" not in context.system_prompt
    assert "System-G" not in context.system_prompt


@pytest.mark.asyncio
async def test_profile_document_embeddings_are_computed_once(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="PocketTrace")
    assembler = make_assembler(profile, embeddings)
    state = SessionState("cached-index")
    state.current_focus = RouteDomain.BUSINESS
    state.turns.append(ChatTurn(role="user", content="PocketTrace"))

    await assembler.build(state)
    await assembler.build(state)

    assert len(embeddings.document_calls) == 1
    assert len(embeddings.query_calls) == 2


@pytest.mark.asyncio
async def test_retrieval_query_keeps_small_recent_context_for_followups(
    profile: BusinessProfile,
) -> None:
    embeddings = RecordingEmbeddings(target="Xarlatan")
    assembler = make_assembler(profile, embeddings)
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

    query = embeddings.query_calls[0]
    assert "Contame sobre Xarlatan" in query
    assert "¿Y qué lenguaje usa ahí?" in query
    assert any(document_id.startswith("projects.") for document_id in context.document_ids)
