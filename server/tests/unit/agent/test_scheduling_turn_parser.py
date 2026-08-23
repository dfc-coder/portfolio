from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.profile import BusinessProfile
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.turn_parser import SchedulingIntent, SchedulingTurnParser


class TrackingLlm:
    def __init__(self, response: str = '{"intent":"other","visitor_name":null,"subject":null}') -> None:
        self.response = response
        self.calls: list[tuple[list[dict], GenerationConfig, object]] = []

    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        self.calls.append((messages, config, response_schema))
        return self.response

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        if False:
            yield ""

    async def health(self) -> bool:
        return True


def make_parser(profile: BusinessProfile, llm: TrackingLlm) -> SchedulingTurnParser:
    return SchedulingTurnParser(
        llm,
        SchedulingPolicy(profile.scheduling),
        GenerationConfig(temperature=0.0, max_tokens=64, top_p=1.0, top_k=1),
    )


@pytest.mark.asyncio
async def test_ordinal_slot_is_deterministic(profile: BusinessProfile) -> None:
    llm = TrackingLlm()
    parser = make_parser(profile, llm)
    state = SessionState("slot")
    state.active_workflow = ActiveWorkflow.SCHEDULING

    turn = await parser.parse(state, "El segundo", RouteRelation.CONTINUE)

    assert turn.intent == SchedulingIntent.SELECT
    assert turn.slot_id == "S2"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_combined_details_are_extracted_without_llm(profile: BusinessProfile) -> None:
    llm = TrackingLlm()
    parser = make_parser(profile, llm)
    state = SessionState("details")

    turn = await parser.parse(
        state,
        "S2. Soy Ana, ana@example.com, para hablar de arquitectura",
        RouteRelation.CONTINUE,
    )

    assert turn.intent == SchedulingIntent.SELECT
    assert turn.slot_id == "S2"
    assert turn.visitor_name == "Ana"
    assert turn.visitor_email == "ana@example.com"
    assert turn.subject == "arquitectura"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_relative_date_is_resolved_without_llm(profile: BusinessProfile) -> None:
    llm = TrackingLlm()
    parser = make_parser(profile, llm)
    state = SessionState("date")
    today = datetime.now(ZoneInfo(profile.scheduling.timezone)).date()

    turn = await parser.parse(state, "Mañana", RouteRelation.CONTINUE)

    assert turn.intent == SchedulingIntent.INFORM
    assert turn.start_date == date.fromordinal(today.toordinal() + 1)
    assert turn.end_date == turn.start_date
    assert llm.calls == []


@pytest.mark.asyncio
async def test_meeting_request_is_deterministic(profile: BusinessProfile) -> None:
    llm = TrackingLlm()
    parser = make_parser(profile, llm)
    state = SessionState("request")

    turn = await parser.parse(state, "Quiero una reunión", RouteRelation.NEW)

    assert turn.intent == SchedulingIntent.REQUEST
    assert llm.calls == []


@pytest.mark.asyncio
async def test_professional_interruption_uses_minimal_semantic_fallback(
    profile: BusinessProfile,
) -> None:
    llm = TrackingLlm()
    parser = make_parser(profile, llm)
    state = SessionState("interrupt")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    tz = ZoneInfo(profile.scheduling.timezone)
    state.scheduling.offered_slots = {
        "S1": OfferedSlot(
            start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
        )
    }
    state.scheduling.visitor_email = "already-known@example.com"

    turn = await parser.parse(state, "¿Podés usar herramientas?", RouteRelation.INTERRUPT)

    assert turn.intent == SchedulingIntent.OTHER
    assert len(llm.calls) == 1
    messages, config, _schema = llm.calls[0]
    assert config.temperature == 0.0
    serialized = "\n".join(str(message["content"]) for message in messages)
    assert "OFFERED_SLOT_IDS" in serialized
    assert "VISITOR_MESSAGE" in serialized
    assert "already-known@example.com" not in serialized
    assert "has_email" not in serialized
    assert "pending_booking" not in serialized
