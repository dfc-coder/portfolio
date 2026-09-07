from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncOpenAI

CAPABILITY_PORTFOLIO = "portfolio"
CAPABILITY_DATETIME = "datetime"
CAPABILITY_REMINDER = "reminder"
CAPABILITIES = (
    CAPABILITY_PORTFOLIO,
    CAPABILITY_DATETIME,
    CAPABILITY_REMINDER,
)

_GATE_TOOL = {
    "type": "function",
    "function": {
        "name": "select_capabilities",
        "description": "Select the minimum external capabilities required for the current visitor request.",
        "parameters": {
            "type": "object",
            "properties": {
                "portfolio": {"type": "boolean"},
                "datetime": {"type": "boolean"},
                "reminder": {"type": "boolean"},
            },
            "required": ["portfolio", "datetime", "reminder"],
            "additionalProperties": False,
        },
    },
}

_GATE_PROMPT = """You are a capability eligibility gate for a portfolio assistant.

Decide which external capabilities are required to satisfy the CURRENT visitor message. Consider recent conversation only to resolve follow-ups.

Capabilities:
- portfolio: factual retrieval about the portfolio subject's professional background, experience, projects, skills, education, certifications, services, or capabilities.
- datetime: deterministic date/time resolution or calendar arithmetic that is required to answer the current request.
- reminder: creating or changing a reminder. Questions merely asking what reminders are or whether they are real do not require this capability.

Rules:
- Select the minimum set required.
- General conversation, greetings, thanks, jokes, creative requests, definitions, and general knowledge require no capability.
- If the exact information needed is already present in recent conversation, do not select a capability just to retrieve it again.
- A mixed request may require more than one capability.
- Do not answer the visitor. Only call select_capabilities.
"""


@dataclass(frozen=True)
class CapabilityDecision:
    names: tuple[str, ...]
    latency_ms: float
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None

    def trace(self) -> dict[str, Any]:
        return {
            "eligible": list(self.names),
            "latency_ms": round(self.latency_ms, 3),
            "finish_reason": self.finish_reason,
            "usage": self.usage,
        }


class CapabilitySelector(Protocol):
    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> CapabilityDecision: ...


class ModelCapabilitySelector:
    def __init__(self, chat: AsyncOpenAI, *, model: str) -> None:
        self._chat = chat
        self._model = model

    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> CapabilityDecision:
        started = time.perf_counter()
        response = await self._chat.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _GATE_PROMPT},
                {"role": "user", "content": _gate_input(message, context)},
            ],
            tools=[_GATE_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "select_capabilities"},
            },
            parallel_tool_calls=False,
            temperature=0,
            max_tokens=64,
        )

        if not response.choices:
            raise RuntimeError("capability gate returned no choices")

        choice = response.choices[0]
        calls = choice.message.tool_calls or []
        if len(calls) != 1 or calls[0].function.name != "select_capabilities":
            raise RuntimeError("capability gate returned an invalid selection")

        try:
            payload = json.loads(calls[0].function.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("capability gate returned invalid JSON") from exc

        names = _capability_names(payload)
        usage = _model_dump(getattr(response, "usage", None))
        return CapabilityDecision(
            names=names,
            latency_ms=(time.perf_counter() - started) * 1000,
            finish_reason=choice.finish_reason,
            usage=usage,
        )


def all_capabilities() -> CapabilityDecision:
    return CapabilityDecision(names=CAPABILITIES, latency_ms=0.0)


def _capability_names(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        raise RuntimeError("capability gate arguments must be an object")

    expected = set(CAPABILITIES)
    if set(payload) != expected:
        raise RuntimeError("capability gate returned unexpected fields")

    for name in CAPABILITIES:
        if not isinstance(payload[name], bool):
            raise RuntimeError(f"capability gate field {name} must be boolean")

    return tuple(name for name in CAPABILITIES if payload[name])


def _gate_input(message: str, context: list[dict[str, Any]]) -> str:
    recent = context[-8:]
    lines = ["Recent conversation:"]
    if not recent:
        lines.append("(none)")

    for item in recent:
        role = str(item.get("role", "unknown"))
        content = item.get("content")
        if content is None and item.get("tool_calls"):
            content = "[assistant requested an external capability]"
        if content is None:
            continue
        lines.append(f"{role}: {content}")

    lines.append("")
    lines.append(f"Current visitor message: {message}")
    return "\n".join(lines)


def _model_dump(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return None
    payload = dump(exclude_none=True)
    return payload if isinstance(payload, dict) else None
