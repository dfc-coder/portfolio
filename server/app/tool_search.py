from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .reranker import Reranker
from .tools import TOOLS

_MIN_RELEVANCE = 0.5
_MAX_CONTEXT_ITEMS = 4

_SEARCH_INSTRUCTION = (
    "Decide which Documents are required to satisfy the CURRENT visitor request. "
    "Each Document describes either direct response or one external tool. "
    "Rank a tool relevant only when the assistant needs that tool's information or action to answer correctly. "
    "A related noun is not enough. Respect negation and information already present in recent context."
)

_DIRECT_RESPONSE = (
    "Direct response without an external tool. Use when the request is ordinary conversation, general "
    "knowledge, asks about the assistant or the portfolio itself, asks what capabilities are available, "
    "or can be answered exactly from information already present in recent context. Do not use direct "
    "response for unverified factual claims about the portfolio subject or for external information/actions "
    "that are not already available in context."
)


@dataclass(frozen=True)
class ToolSelection:
    tools: list[dict[str, Any]]
    scores: dict[str, float]
    latency_ms: float

    def trace(self) -> dict[str, Any]:
        return {
            "selected": [tool_name(tool) for tool in self.tools],
            "scores": self.scores,
            "latency_ms": round(self.latency_ms, 3),
        }


class ToolSearch:
    def __init__(self, reranker: Reranker, *, min_relevance: float = _MIN_RELEVANCE) -> None:
        if not 0.0 <= min_relevance <= 1.0:
            raise ValueError("min_relevance must be between 0 and 1")
        self._reranker = reranker
        self._min_relevance = min_relevance

    async def select(
        self,
        message: str,
        context: list[dict[str, Any]],
    ) -> ToolSelection:
        started = time.perf_counter()
        documents = [_DIRECT_RESPONSE, *[tool_search_text(tool) for tool in TOOLS]]
        scores = await self._reranker.rank(
            _query(message, context),
            documents,
            instruction=_SEARCH_INSTRUCTION,
        )
        if len(scores) != len(documents):
            raise ValueError("reranker score count does not match candidate count")

        direct_score = scores[0]
        tool_scores = scores[1:]
        selected = [
            tool
            for tool, score in zip(TOOLS, tool_scores, strict=True)
            if score >= self._min_relevance and score > direct_score
        ]
        return ToolSelection(
            tools=selected,
            scores={
                "direct_response": round(direct_score, 6),
                **{
                    tool_name(tool): round(score, 6)
                    for tool, score in zip(TOOLS, tool_scores, strict=True)
                },
            },
            latency_ms=(time.perf_counter() - started) * 1000,
        )


def all_tools() -> ToolSelection:
    return ToolSelection(
        tools=list(TOOLS),
        scores={},
        latency_ms=0.0,
    )


def tool_name(tool: dict[str, Any]) -> str:
    return str(tool["function"]["name"])


def tool_search_text(tool: dict[str, Any]) -> str:
    function = tool["function"]
    parameters = function.get("parameters", {})
    properties = parameters.get("properties", {})

    lines = [
        f"Tool: {function['name']}",
        f"Description: {function.get('description', '')}",
    ]
    for name, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        description = str(spec.get("description", "")).strip()
        enum = spec.get("enum")
        suffix = f" Allowed: {', '.join(map(str, enum))}." if isinstance(enum, list) else ""
        lines.append(f"Parameter {name}: {description}{suffix}")
    return "\n".join(lines)


def _query(message: str, context: list[dict[str, Any]]) -> str:
    recent: list[str] = []
    for item in context[-_MAX_CONTEXT_ITEMS:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant", "tool"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "tool":
            content = _compact_tool_result(content)
        recent.append(f"{role}: {content.strip()}")

    parts: list[str] = []
    if recent:
        parts.extend(["Recent context:", *recent])
    parts.extend(["Current visitor request:", message.strip()])
    return "\n".join(parts)


def _compact_tool_result(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content[:1000]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:1000]
