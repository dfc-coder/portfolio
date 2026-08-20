from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.executor import ActionExecutor
from app.domain.conversation import ConversationStage, SessionState
from app.domain.planning import AgentAction, ObservationType, Plan
from app.domain.scheduling import OfferedSlot


class NoopSlots:
    async def available_slots(self, start_date, end_date):  # type: ignore[no-untyped-def]
        del start_date, end_date
        return []


@pytest.mark.asyncio
async def test_select_slot_collects_details_and_requests_next_step() -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    state = SessionState(
        session_id="session-123",
        stage=ConversationStage.SCHEDULING_SLOT,
        offered_slots={
            "S2": OfferedSlot(
                start=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
                end=datetime(2026, 8, 25, 15, 0, tzinfo=tz),
            )
        },
    )
    executor = ActionExecutor(NoopSlots())  # type: ignore[arg-type]

    result = await executor.execute(
        state,
        Plan(
            action=AgentAction.SELECT_SLOT,
            slot_id="S2",
            visitor_name="Juan Perez",
            visitor_email="juan@example.com",
            subject="Architecture discussion",
        ),
    )

    assert result.type == ObservationType.SUCCESS
    assert result.requires_next_step is True
    assert state.selected_slot_id == "S2"
    assert state.visitor_email == "juan@example.com"
