from app.agent.fsm import ConversationFSM
from app.domain.conversation import ConversationStage, SessionState
from app.domain.planning import AgentAction, Observation, ObservationType, Plan


def test_fsm_moves_from_availability_to_slot_selection() -> None:
    fsm = ConversationFSM()
    state = SessionState(session_id="session-123")
    plan = Plan(
        action=AgentAction.GET_AVAILABILITY,
        start_date="2026-08-25",
        end_date="2026-08-25",
    )
    observation = Observation(type=ObservationType.AVAILABLE_SLOTS)

    fsm.transition(state, plan, observation)

    assert state.stage == ConversationStage.SCHEDULING_SLOT
    assert AgentAction.SELECT_SLOT in fsm.allowed_actions(state.stage)
    assert AgentAction.PREPARE_BOOKING not in fsm.allowed_actions(state.stage)
