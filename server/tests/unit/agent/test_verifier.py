from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.scheduler import Scheduler, SchedulingIntent, SchedulingTurn
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.ports.llm import GenerationConfig
from app.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy


class OneTurnLlm:
    async def complete(self, messages, config, response_schema=None):  # type: ignore[no-untyped-def]
        del messages, config, response_schema
        return SchedulingTurn(intent=SchedulingIntent.SELECT, slot_id="S2").model_dump_json()

    async def stream(self, messages, config):  # type: ignore[no-untyped-def]
        del messages, config
        if False:
            yield ""

    async def health(self) -> bool:
        return True


class NeverSlots:
    async def available_slots(self, start_date, end_date):  # type: ignore[no-untyped-def]
        del start_date, end_date
        raise AssertionError("availability should not be queried for an invalid selection")


@pytest.mark.asyncio
async def test_scheduler_rejects_unoffered_slot(profile: BusinessProfile) -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    state = SessionState(session_id="session-123")
    state.active_workflow = ActiveWorkflow.SCHEDULING
    state.scheduling.offered_slots = {
        "S1": OfferedSlot(
            start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
        )
    }
    state.scheduling.requested_start_date = datetime(2026, 8, 25).date()
    state.scheduling.requested_end_date = datetime(2026, 8, 25).date()
    policy = SchedulingPolicy(profile.scheduling)
    scheduler = Scheduler(
        OneTurnLlm(),
        NeverSlots(),  # type: ignore[arg-type]
        InMemoryCalendarGateway(),
        policy,
        GenerationConfig(temperature=0.1, max_tokens=96),
    )

    reply = await scheduler.handle(state, "S2", RouteRelation.CONTINUE)

    assert "no está entre" in reply.text.lower()
    assert state.scheduling.selected_slot_id is None
