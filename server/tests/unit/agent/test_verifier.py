from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.fsm import ConversationFSM
from app.agent.verifier import AgentVerifier
from app.domain.conversation import ConversationStage, SessionState
from app.domain.planning import AgentAction, Plan
from app.domain.scheduling import OfferedSlot


def test_verifier_rejects_unoffered_slot() -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    state = SessionState(
        session_id="session-123",
        stage=ConversationStage.SCHEDULING_SLOT,
        offered_slots={
            "S1": OfferedSlot(
                start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
                end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
            )
        },
    )
    verifier = AgentVerifier(ConversationFSM())

    result = verifier.verify_plan(
        state,
        Plan(action=AgentAction.SELECT_SLOT, slot_id="S2"),
    )

    assert result.ok is False
    assert "not offered" in " ".join(result.issues)
