from __future__ import annotations

import pytest

from app.agent.context import ContextAssembler
from app.agent.knowledge import ProfileDocument, RetrievedDocument
from app.domain.conversation import ChatTurn, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteDomain


@pytest.mark.asyncio
async def test_general_context_has_no_portfolio_identity(
    profile: BusinessProfile,
) -> None:
    assembler = ContextAssembler(profile)
    state = SessionState("general-context")
    state.current_focus = RouteDomain.GENERAL
    state.turns.append(ChatTurn(role="user", content="¿Qué hora es?"))

    context = await assembler.build(state, ())

    assert profile.owner.name not in context.system_prompt
    assert "PORTFOLIO_SUBJECT=" not in context.system_prompt
    assert "PORTFOLIO_KNOWLEDGE:" not in context.system_prompt
    assert "CURRENT_TIME=" in context.system_prompt
    assert context.history[-1].content == "¿Qué hora es?"


@pytest.mark.asyncio
async def test_business_context_contains_only_retrieved_knowledge(
    profile: BusinessProfile,
) -> None:
    assembler = ContextAssembler(profile)
    state = SessionState("business-context")
    state.current_focus = RouteDomain.BUSINESS
    state.turns.append(
        ChatTurn(role="user", content="Contame sobre PocketTrace")
    )
    retrieved = (
        RetrievedDocument(
            document=ProfileDocument(
                document_id="projects.3",
                text='{"project":{"name":"PocketTrace","stack":["Rust"]}}',
            ),
            score=0.92,
        ),
    )

    context = await assembler.build(state, retrieved)

    assert f"PORTFOLIO_SUBJECT={profile.owner.name}" in context.system_prompt
    assert "PORTFOLIO_KNOWLEDGE:" in context.system_prompt
    assert "PocketTrace" in context.system_prompt
    assert "CURRENT_TIME=" in context.system_prompt
    assert context.document_ids == ("projects.3",)
