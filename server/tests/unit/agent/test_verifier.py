from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.safety import CapabilitySafetyGate
from app.domain.capabilities import CapabilityKind, CapabilitySpec
from app.domain.conversation import SessionState
from app.domain.routing import RouteDomain
from app.domain.scheduling import OfferedSlot
from app.domain.semantics import DialogueAct, SchedulingCommand
from app.profile import BusinessProfile
from app.scheduling.policy import SchedulingPolicy


def test_safety_gate_rejects_unoffered_slot(profile: BusinessProfile) -> None:
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    state = SessionState(session_id="session-123")
    state.scheduling.offered_slots = {
        "S1": OfferedSlot(
            start=datetime(2026, 8, 25, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 25, 14, 30, tzinfo=tz),
        )
    }
    capability = CapabilitySpec(
        name="scheduling.select_slot",
        description="select",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.SELECT}),
        kind=CapabilityKind.INTERNAL,
    )
    result = CapabilitySafetyGate(SchedulingPolicy(profile.scheduling)).validate(
        capability,
        state,
        SchedulingCommand(act=DialogueAct.SELECT, slot_id="S2"),
        "el segundo",
    )
    assert result.ok is False
    assert "not offered" in " ".join(result.issues)
