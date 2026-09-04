from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .portfolio import Portfolio
from .prompt import build_messages
from .tools import TOOLS, run_tool_call

MAX_TOOL_ROUNDS = 6
AgentEvent = tuple[str, dict[str, object]]

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        subject: str,
        chat: AsyncOpenAI,
        portfolio: Portfolio,
        *,
        model: str,
        timezone: str,
        temperature: float = 0.2,
        max_tokens: int = 180,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._portfolio = portfolio
        self._model = model
        self._timezone = timezone
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def respond(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> AsyncIterator[AgentEvent]:
        messages: list[dict[str, Any]] = build_messages(
            self._subject,
            history[-6:],
            message,
        )

        for round_number in range(1, MAX_TOOL_ROUNDS + 2):
            yield "status", {"phase": "thinking", "round": round_number}
            started = time.perf_counter()
            stream = await self._chat.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=True,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                stream=True,
            )

            content: list[str] = []
            calls: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None
            responding = False

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason

                delta = choice.delta
                text = delta.content or ""
                if text:
                    if not responding:
                        responding = True
                        yield "status", {"phase": "responding", "round": round_number}
                    content.append(text)
                    yield "token", {"text": text}

                for call in delta.tool_calls or []:
                    item = calls.setdefault(
                        call.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if call.id:
                        item["id"] += call.id
                    if call.function:
                        if call.function.name:
                            item["name"] += call.function.name
                        if call.function.arguments:
                            item["arguments"] += call.function.arguments

            ordered_calls = [calls[index] for index in sorted(calls)]
            tool_names = [call["name"] for call in ordered_calls]
            logger.info(
                "agent round=%s finish=%s tools=%s latency_ms=%d",
                round_number,
                finish_reason,
                ",".join(tool_names) or "-",
                int((time.perf_counter() - started) * 1000),
            )

            messages.append(
                _assistant_message(
                    "".join(content) or None,
                    ordered_calls,
                )
            )

            if not ordered_calls:
                if not "".join(content).strip():
                    raise RuntimeError("LLM returned an empty response")
                return

            if round_number > MAX_TOOL_ROUNDS:
                raise RuntimeError("tool loop limit reached")

            for call in ordered_calls:
                yield "tool", {
                    "name": call["name"],
                    "state": "running",
                    "round": round_number,
                }

            results = await asyncio.gather(
                *(
                    run_tool_call(
                        call["id"],
                        call["name"],
                        call["arguments"],
                        self._portfolio,
                        self._timezone,
                    )
                    for call in ordered_calls
                )
            )

            for call, result in zip(ordered_calls, results, strict=True):
                yield "tool", {
                    "name": call["name"],
                    "state": "done",
                    "ok": _tool_ok(result),
                    "round": round_number,
                }

            messages.extend(results)

        raise RuntimeError("tool loop limit reached")


def _tool_ok(message: dict[str, str]) -> bool:
    try:
        body = json.loads(message["content"])
    except (KeyError, json.JSONDecodeError, TypeError):
        return False
    return bool(body.get("ok"))


def _assistant_message(
    content: str | None,
    calls: list[dict[str, str]],
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if calls:
        message["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in calls
        ]
    return message
