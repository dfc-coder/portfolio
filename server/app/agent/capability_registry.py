from __future__ import annotations

from app.domain.capabilities import CapabilityKind, CapabilitySpec, SideEffect
from app.domain.routing import RouteDomain
from app.domain.semantics import DialogueAct, SchedulingCommand


_SCHEDULING_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        name="scheduling.cancel",
        description="Cancel and clear the active scheduling workflow without changing an already-created calendar event.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.CANCEL}),
        kind=CapabilityKind.INTERNAL,
        requires_all=frozenset({"active_workflow"}),
    ),
    CapabilitySpec(
        name="calendar.create_booking",
        description="Create the already-prepared pending booking after an explicit visitor confirmation.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.CONFIRM}),
        kind=CapabilityKind.TOOL,
        requires_all=frozenset({"pending_booking", "semantic_confirmation", "explicit_confirmation"}),
        side_effect=SideEffect.WRITE,
        requires_confirmation=True,
    ),
    CapabilitySpec(
        name="scheduling.confirmation_required",
        description="Remind the visitor that the prepared booking still needs an explicit confirmation.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.CONFIRM, DialogueAct.REQUEST, DialogueAct.INFORM, DialogueAct.SELECT}),
        kind=CapabilityKind.RESPOND,
        requires_all=frozenset({"pending_booking"}),
        forbids=frozenset({"explicit_confirmation"}),
    ),
    CapabilitySpec(
        name="scheduling.select_slot",
        description="Select one slot from the availability choices already offered in this conversation.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.SELECT}),
        kind=CapabilityKind.INTERNAL,
        requires_all=frozenset({"offered_slots", "slot_reference"}),
    ),
    CapabilitySpec(
        name="calendar.search_availability",
        description="Read Diego's calendar availability for a date or date range supplied by the visitor.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.REQUEST, DialogueAct.INFORM}),
        kind=CapabilityKind.TOOL,
        requires_all=frozenset({"date_range"}),
        requires_any=frozenset({"date_input", "no_offered_slots"}),
        side_effect=SideEffect.READ,
    ),
    CapabilitySpec(
        name="scheduling.prepare_booking",
        description="Prepare a booking draft after a valid slot and all visitor details are known; do not write the calendar yet.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.SELECT, DialogueAct.INFORM}),
        kind=CapabilityKind.INTERNAL,
        requires_all=frozenset({"selected_slot", "details_complete"}),
        forbids=frozenset({"pending_booking"}),
    ),
    CapabilitySpec(
        name="scheduling.ask_details",
        description="Ask only for the missing visitor name, email, or meeting subject after a slot has been selected.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.SELECT, DialogueAct.INFORM}),
        kind=CapabilityKind.RESPOND,
        requires_all=frozenset({"selected_slot"}),
        forbids=frozenset({"details_complete", "pending_booking"}),
    ),
    CapabilitySpec(
        name="scheduling.ask_slot",
        description="Remind the visitor to choose one of the already offered slots while preserving any details they supplied.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.REQUEST, DialogueAct.INFORM}),
        kind=CapabilityKind.RESPOND,
        requires_all=frozenset({"offered_slots"}),
        forbids=frozenset({"selected_slot", "pending_booking", "date_input"}),
    ),
    CapabilitySpec(
        name="scheduling.ask_dates",
        description="Ask the visitor for a meeting date or date range because scheduling has started but no usable date range is known.",
        domain=RouteDomain.SCHEDULING,
        acts=frozenset({DialogueAct.REQUEST, DialogueAct.INFORM}),
        kind=CapabilityKind.RESPOND,
        requires_all=frozenset({"active_workflow"}),
        forbids=frozenset({"date_range", "pending_booking"}),
    ),
)


class CapabilityRegistry:
    def __init__(self, capabilities: tuple[CapabilitySpec, ...] = _SCHEDULING_CAPABILITIES) -> None:
        self._capabilities = capabilities

    def eligible(
        self,
        domain: RouteDomain,
        command: SchedulingCommand,
        facts: frozenset[str],
        excluded: frozenset[str] = frozenset(),
    ) -> tuple[CapabilitySpec, ...]:
        return tuple(
            capability
            for capability in self._capabilities
            if capability.name not in excluded
            and capability.domain == domain
            and command.act in capability.acts
            and capability.applicable(facts)
        )
