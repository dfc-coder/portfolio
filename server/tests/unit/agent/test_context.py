from __future__ import annotations

import pytest

from app.agent.context import ContextAssembler
from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import Route
from app.portfolio.search import Fact


def make_assembler(profile: BusinessProfile) -> ContextAssembler:
    return ContextAssembler(
        profile,
        ("Answer questions about Diego's professional work.",),
    )


@pytest.mark.asyncio
async def test_conversation_context_does_not_expose_portfolio_identity(
    profile: BusinessProfile,
) -> None:
    assembler = make_assembler(profile)
    state = SessionState("conversation-context")
    state.current_focus = Route.CONVERSATION
    state.turns.append(ChatTurn(role="user", content="Hola"))

    context = await assembler.build(state)

    assert context.document_ids == ()
    assert "\nRELEVANT_KNOWLEDGE:\n" not in context.system_prompt
    assert profile.owner.name not in context.system_prompt
    assert profile.representative.disclosure not in context.system_prompt
    assert "PORTFOLIO_SUBJECT=" not in context.system_prompt
    assert "AGENT_CAPABILITIES:" not in context.system_prompt
    assert "OWNER_POLICY:" not in context.system_prompt
    assert "website assistant speaking with a visitor" in context.system_prompt
    assert context.history[-1].content == "Hola"


@pytest.mark.asyncio
async def test_portfolio_context_contains_only_supplied_evidence(
    profile: BusinessProfile,
) -> None:
    assembler = make_assembler(profile)
    state = SessionState("portfolio-context")
    state.current_focus = Route.PORTFOLIO
    state.turns.append(
        ChatTurn(
            role="user",
            content="¿Qué proyecto funciona como inspector local de trazas?",
        )
    )
    evidence = (
        Fact(
            source="projects.0",
            text='{"project":{"name":"PocketTrace","stack":["Rust"]}}',
        ),
    )

    context = await assembler.build(state, evidence)

    assert context.document_ids == ("projects.0",)
    assert f"PORTFOLIO_SUBJECT={profile.owner.name}" in context.system_prompt
    assert "PORTFOLIO_SUBJECT is the professional being discussed" in context.system_prompt
    assert "PocketTrace" in context.system_prompt
    assert "Xarlatan" not in context.system_prompt
    assert context.knowledge_chars == len(evidence[0].text)


@pytest.mark.asyncio
async def test_portfolio_context_marks_missing_evidence_explicitly(
    profile: BusinessProfile,
) -> None:
    assembler = make_assembler(profile)
    state = SessionState("portfolio-empty")
    state.current_focus = Route.PORTFOLIO
    state.turns.append(ChatTurn(role="user", content="¿Tiene certificación XYZ?"))

    context = await assembler.build(state)

    assert "RELEVANT_KNOWLEDGE:\n<none>" in context.system_prompt
    assert context.document_ids == ()
    assert context.knowledge_chars == 0
