from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .portfolio import Portfolio
from .prompt import build_messages
from .tools import TOOLS, run_tool_call

MAX_TOOL_ROUNDS = 6


class Agent:
    def __init__(
        self,
        subject: str,
        chat: AsyncOpenAI,
        portfolio: Portfolio,
        *,
        model: str,
        timezone: str,
        temperature: float = 0.65,
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
    ) -> AsyncIterator[str]:
        messages: list[dict[str, Any]] = build_messages(
            self._subject,
            history[-6:],
            message,
        )

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._chat.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=True,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            if not response.choices:
                raise RuntimeError("LLM returned no choices")

            assistant = response.choices[0].message
            messages.append(_assistant_message(assistant))

            calls = assistant.tool_calls or []
            if not calls:
                text = assistant.content or ""
                if not text.strip():
                    raise RuntimeError("LLM returned an empty response")
                yield text
                return

            results = await asyncio.gather(
                *(
                    run_tool_call(
                        call.id,
                        call.function.name,
                        call.function.arguments,
                        self._portfolio,
                        self._timezone,
                    )
                    for call in calls
                )
            )
            messages.extend(results)

        raise RuntimeError("tool loop limit reached")


def _assistant_message(message: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.content,
    }

    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ]

    return result
