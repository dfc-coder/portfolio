from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .routing import RouteDomain
from .semantics import DialogueAct


class CapabilityKind(StrEnum):
    RESPOND = "respond"
    INTERNAL = "internal"
    TOOL = "tool"


class SideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    domain: RouteDomain
    acts: frozenset[DialogueAct]
    kind: CapabilityKind
    requires_all: frozenset[str] = field(default_factory=frozenset)
    requires_any: frozenset[str] = field(default_factory=frozenset)
    forbids: frozenset[str] = field(default_factory=frozenset)
    side_effect: SideEffect = SideEffect.NONE
    requires_confirmation: bool = False

    def applicable(self, facts: frozenset[str]) -> bool:
        if not self.requires_all.issubset(facts):
            return False
        if self.requires_any and not self.requires_any.intersection(facts):
            return False
        if self.forbids.intersection(facts):
            return False
        return True
