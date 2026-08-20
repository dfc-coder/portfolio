from __future__ import annotations

from typing import Any

import pytest

from app.agent import BusinessRepresentative
from app.calendar_gateway import InMemoryCalendarGateway
from app.policies import SchedulingPolicy
from app.profile import BusinessProfile
from app.session import SessionStore
from app.slot_service import SlotService


class NoopLlama:
    pass


def build_agent(
    profile: BusinessProfile,
) -> tuple[BusinessRepresentative, SessionStore]:
    sessions = SessionStore()
    policy = SchedulingPolicy(profile.scheduling)
    calendar = InMemoryCalendarGateway()
    agent = BusinessRepresentative(
        profile,
        sessions,
        policy,
        SlotService(calendar, policy),
        calendar,
        NoopLlama(),  # type: ignore[arg-type]
    )
    return agent, sessions


@pytest.mark.asyncio
async def test_messages_have_exactly_one_leading_system_message(
    profile: BusinessProfile,
) -> None:
    agent, sessions = build_agent(profile)
    state = await sessions.get("message-test-001")
    await sessions.append_turn(state, "user", "Hola")
    await sessions.append_turn(state, "assistant", "Hola, ¿en qué puedo ayudarte?")

    messages = agent._messages(state)  # noqa: SLF001 - template contract test

    assert messages[0]["role"] == "system"
    assert sum(message["role"] == "system" for message in messages) == 1
    assert "BUSINESS_CONTEXT=" in messages[0]["content"]
    assert "CURRENT_TIME=" in messages[0]["content"]
    assert f"TIMEZONE={profile.scheduling.timezone}" in messages[0]["content"]
    assert [message["role"] for message in messages[1:]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_dynamic_system_context_is_merged_into_first_message(
    profile: BusinessProfile,
) -> None:
    agent, sessions = build_agent(profile)
    state = await sessions.get("message-test-002")
    await sessions.append_turn(state, "user", "Sí, confirmo")
    suffix = "CALENDAR_WRITE_SUCCEEDED booking-123"

    messages: list[dict[str, Any]] = agent._messages(  # noqa: SLF001
        state,
        system_suffix=suffix,
    )

    assert messages[0]["role"] == "system"
    assert suffix in messages[0]["content"]
    assert sum(message["role"] == "system" for message in messages) == 1
    assert messages[1]["role"] == "user"
