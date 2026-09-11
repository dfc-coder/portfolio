from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .conversation import trim_messages
from .portfolio import Portfolio
from .prompt import build_messages
from .tools import TOOL_SCHEMAS, execute_tool
from .trace import finish_round, finish_trace, new_trace, record_final_ttft, record_tool, start_round

MAX_TOOL_ROUNDS = 4
AgentEvent = tuple[str, dict[str, object]]


class Agent:
    def __init__(
        self,
        subject: str,
        chat: AsyncOpenAI,
        portfolio: Portfolio,
        *,
        model: str,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 1,
        min_p: float = 0.0,
        presence_penalty: float = 0.0,
        repeat_penalty: float = 1.0,
        max_tokens: int = 256,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._portfolio = portfolio
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._min_p = min_p
        self._presence_penalty = presence_penalty
        self._repeat_penalty = repeat_penalty
        self._max_tokens = max_tokens

    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        history = trim_messages(context)
        conversation = [*history, {"role": "user", "content": message}]
        messages = build_messages(self._subject, history, message)
        trace = new_trace(message, context, self._model) if diagnostics else None

        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 2):
                yield "status", {"phase": "model", "round": round_number}
                round_started = time.perf_counter()
                round_trace = start_round(trace, round_number)

                stream = await self._chat.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=list(TOOL_SCHEMAS),
                    parallel_tool_calls=False,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    presence_penalty=self._presence_penalty,
                    max_tokens=self._max_tokens,
                    stream=True,
                    extra_body={
                        "top_k": self._top_k,
                        "min_p": self._min_p,
                        "repeat_penalty": self._repeat_penalty,
                    },
                )

                mode: str | None = None
                pending_text: list[str] = []
                answer_parts: list[str] = []
                calls: dict[int, dict[str, str]] = {}
                finish_reason: str | None = None

                async for chunk in stream:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue

                    choice = choices[0]
                    if getattr(choice, "finish_reason", None) is not None:
                        finish_reason = choice.finish_reason

                    delta = choice.delta
                    tool_deltas = getattr(delta, "tool_calls", None) or []
                    text = getattr(delta, "content", None) or ""

                    if tool_deltas:
                        if mode == "final":
                            raise RuntimeError("model mixed final text with tool calls")
                        mode = "tool"
                        pending_text.clear()
                        _merge_tool_calls(calls, tool_deltas)

                    if not text:
                        continue

                    if mode == "tool":
                        if text.strip():
                            raise RuntimeError("model mixed final text with tool calls")
                        continue

                    if mode is None:
                        pending_text.append(text)
                        buffered = "".join(pending_text)
                        if not buffered.strip():
                            continue
                        mode = "final"
                        pending_text.clear()
                        answer_parts.append(buffered)
                        record_final_ttft(trace)
                        yield "status", {"phase": "responding", "round": round_number}
                        yield "token", {"text": buffered}
                        continue

                    answer_parts.append(text)
                    yield "token", {"text": text}

                finish_round(round_trace, finish_reason, round_started)

                if mode == "final":
                    answer = "".join(answer_parts).strip()
                    if not answer:
                        raise RuntimeError("model returned an empty answer")

                    conversation.append({"role": "assistant", "content": answer})
                    returned_context = trim_messages(conversation)
                    yield "context", {"messages": returned_context}
                    if trace is not None:
                        yield "trace", finish_trace(trace, answer, returned_context, None)
                    return

                if mode != "tool" or not calls:
                    raise RuntimeError("model returned no answer and no tool call")
                if round_number > MAX_TOOL_ROUNDS:
                    raise RuntimeError("tool loop limit reached")

                ordered_calls = _ordered_calls(calls)
                assistant_message = _assistant_tool_message(ordered_calls)
                messages.append(assistant_message)
                conversation.append(assistant_message)

                for call in ordered_calls:
                    yield "tool", {
                        "name": call["name"],
                        "state": "running",
                        "round": round_number,
                    }
                    tool_started = time.perf_counter()
                    result = await execute_tool(
                        call["name"],
                        call["arguments"],
                        self._portfolio,
                        user_message=message,
                    )
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                    messages.append(tool_message)
                    conversation.append(tool_message)
                    record_tool(round_trace, call, result, tool_started)
                    yield "tool", {
                        "name": call["name"],
                        "state": "done",
                        "ok": bool(result.get("ok")),
                        "round": round_number,
                    }

            raise RuntimeError("tool loop limit reached")
        except Exception as exc:
            if trace is not None:
                yield "trace", finish_trace(
                    trace,
                    None,
                    None,
                    {"type": type(exc).__name__, "message": str(exc)},
                )
            raise


def _merge_tool_calls(calls: dict[int, dict[str, str]], deltas: list[Any]) -> None:
    for delta in deltas:
        item = calls.setdefault(delta.index, {"id": "", "name": "", "arguments": ""})
        if getattr(delta, "id", None):
            item["id"] += delta.id
        function = getattr(delta, "function", None)
        if function is None:
            continue
        if getattr(function, "name", None):
            item["name"] += function.name
        if getattr(function, "arguments", None):
            item["arguments"] += function.arguments


def _ordered_calls(calls: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    ordered = [calls[index] for index in sorted(calls)]
    for call in ordered:
        if not call["id"] or not call["name"]:
            raise RuntimeError("model returned an incomplete tool call")
    return ordered


def _assistant_tool_message(calls: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in calls
        ],
    }
