from __future__ import annotations

from app.domain.conversation import ConversationStage, SessionState
from app.domain.planning import AgentAction, Observation, ObservationType, Plan


class ConversationFSM:
    _ALLOWED: dict[ConversationStage, frozenset[AgentAction]] = {
        ConversationStage.BUSINESS: frozenset(
            {AgentAction.ANSWER, AgentAction.ASK_FOR_DATES, AgentAction.GET_AVAILABILITY}
        ),
        ConversationStage.SCHEDULING_DATES: frozenset(
            {
                AgentAction.ASK_FOR_DATES,
                AgentAction.GET_AVAILABILITY,
                AgentAction.CANCEL_BOOKING,
            }
        ),
        ConversationStage.SCHEDULING_SLOT: frozenset(
            {
                AgentAction.SELECT_SLOT,
                AgentAction.GET_AVAILABILITY,
                AgentAction.ASK_FOR_DATES,
                AgentAction.CANCEL_BOOKING,
            }
        ),
        ConversationStage.SCHEDULING_DETAILS: frozenset(
            {
                AgentAction.SELECT_SLOT,
                AgentAction.ASK_FOR_DETAILS,
                AgentAction.PREPARE_BOOKING,
                AgentAction.CANCEL_BOOKING,
            }
        ),
        ConversationStage.SCHEDULING_CONFIRMATION: frozenset({AgentAction.CANCEL_BOOKING}),
        ConversationStage.COMPLETE: frozenset(
            {AgentAction.ANSWER, AgentAction.ASK_FOR_DATES, AgentAction.GET_AVAILABILITY}
        ),
    }

    def allowed_actions(self, stage: ConversationStage) -> frozenset[AgentAction]:
        return self._ALLOWED[stage]

    def transition(self, state: SessionState, plan: Plan, observation: Observation) -> None:
        if plan.action == AgentAction.ASK_FOR_DATES:
            state.stage = ConversationStage.SCHEDULING_DATES
            return
        if plan.action == AgentAction.GET_AVAILABILITY:
            state.stage = (
                ConversationStage.SCHEDULING_SLOT
                if observation.type == ObservationType.AVAILABLE_SLOTS
                else ConversationStage.SCHEDULING_DATES
            )
            return
        if plan.action == AgentAction.SELECT_SLOT:
            state.stage = ConversationStage.SCHEDULING_DETAILS
            return
        if plan.action == AgentAction.ASK_FOR_DETAILS:
            state.stage = ConversationStage.SCHEDULING_DETAILS
            return
        if plan.action == AgentAction.PREPARE_BOOKING:
            state.stage = (
                ConversationStage.SCHEDULING_CONFIRMATION
                if observation.type == ObservationType.AWAITING_CONFIRMATION
                else ConversationStage.SCHEDULING_DETAILS
            )
            return
        if plan.action == AgentAction.CANCEL_BOOKING:
            state.stage = ConversationStage.BUSINESS
            return
        if plan.action == AgentAction.ANSWER:
            state.stage = ConversationStage.BUSINESS
