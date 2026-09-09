from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .reranker import Reranker
from .tools import TOOLS

_MIN_RELEVANCE = 0.5
_MAX_CONTEXT_ITEMS = 4

_NEED_TOOL_INSTRUCTION = (
    "Choose which Document best describes how the CURRENT visitor request must be answered. "
    "Judge necessity, not topical similarity. Respect recent context and explicit negation."
)
_DIRECT_RESPONSE = (
    "Answer directly without any external capability. This applies to ordinary conversation, general "
    "knowledge, questions about the assistant or portfolio itself, questions about available capabilities, "
    "and requests already answered exactly by recent context."
)
_EXTERNAL_RESPONSE = (
    "An external capability is necessary because the request needs authoritative information not already "
    "present in the conversation, a current or computed external value, or an external action."
)

_TOOL_SEARCH_INSTRUCTION = (
    "The CURRENT visitor request requires at least one external capability. Rank each Document by whether "
    "that tool provides information or an action required by the request. Rank unrelated tools low. "
    "Multiple tools may be required. Use only the Document's declared capability."
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
        query = _query(message, context)

        need_scores = await self._reranker.rank(
            query,
            [_DIRECT_RESPONSE, _EXTERNAL_RESPONSE],
            instruction=_NEED_TOOL_INSTRUCTION,
        )
        if len(need_scores) != 2:
            raise ValueError("reranker score count does not match necessity candidates")

        direct_score, external_score = need_scores
        trace_scores: dict[str, float] = {
            "direct_response": round(direct_score, 6),
            "external_required": round(external_score, 6),
        }

        if direct_score >= external_score:
            return ToolSelection(
                tools=[],
                scores=trace_scores,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        documents = [tool_search_text(tool) for tool in TOOLS]
        tool_scores = await self._reranker.rank(
            query,
            documents,
            instruction=_TOOL_SEARCH_INSTRUCTION,
        )
        if len(tool_scores) != len(TOOLS):
            raise ValueError("reranker score count does not match tool count")

        selected = [
            tool
            for tool, score in zip(TOOLS, tool_scores, strict=True)
            if score >= self._min_relevance
        ]
        trace_scores.update(
            {
                tool_name(tool): round(score, 6)
                for tool, score in zip(TOOLS, tool_scores, strict=True)
            }
        )
        return ToolSelection(
            tools=selected,
            scores=trace_scores,
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
