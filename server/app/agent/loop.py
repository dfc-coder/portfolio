from __future__ import annotations

import logging

from app.domain.planning import Observation, ObservationType
from app.domain.routing import RouteDomain
from app.domain.semantics import SchedulingCommand

from .belief import BeliefUpdater
from .capability_executor import CapabilityExecutor
from .capability_registry import CapabilityRegistry
from .safety import CapabilitySafetyGate
from .selector import CapabilitySelector

logger = logging.getLogger(__name__)


class BoundedCapabilityLoop:
    def __init__(
        self,
        belief: BeliefUpdater,
        registry: CapabilityRegistry,
        selector: CapabilitySelector,
        safety: CapabilitySafetyGate,
        executor: CapabilityExecutor,
        *,
        max_steps: int = 3,
        max_repairs: int = 1,
    ) -> None:
        self._belief = belief
        self._registry = registry
        self._selector = selector
        self._safety = safety
        self._executor = executor
        self._max_steps = max(1, max_steps)
        self._max_repairs = max(0, max_repairs)

    async def run(
        self,
        state,
        command: SchedulingCommand,
        user_message: str,
    ) -> Observation:
        excluded: set[str] = set()
        repairs = 0

        for step in range(1, self._max_steps + 1):
            facts = set(self._belief.facts(state, command))
            if self._safety._policy.is_explicit_confirmation(user_message):
                facts.add("explicit_confirmation")
            frozen_facts = frozenset(facts)

            candidates = self._registry.eligible(
                RouteDomain.SCHEDULING,
                command,
                frozen_facts,
                frozenset(excluded),
            )
            if not candidates:
                logger.info(
                    "capability_loop terminal=no_capability step=%s act=%s facts=%s",
                    step,
                    command.act.value,
                    sorted(frozen_facts),
                )
                return Observation(type=ObservationType.SUCCESS, data={"not_applicable": True})

            capability = await self._selector.select(command, frozen_facts, candidates)
            validation = self._safety.validate(capability, state, command, user_message)
            if not validation.ok:
                logger.warning(
                    "capability_loop validation_failed capability=%s issues=%s",
                    capability.name,
                    validation.issues,
                )
                excluded.add(capability.name)
                if repairs >= self._max_repairs:
                    return Observation(
                        type=ObservationType.TOOL_ERROR,
                        data={"error": "capability_validation_failed", "issues": validation.issues},
                    )
                repairs += 1
                continue

            logger.info(
                "capability_loop step=%s capability=%s act=%s",
                step,
                capability.name,
                command.act.value,
            )
            observation = await self._executor.execute(capability, state, command)
            excluded.add(capability.name)
            if not observation.requires_next_step:
                return observation

        return Observation(type=ObservationType.TOOL_ERROR, data={"error": "max_steps_exceeded"})
