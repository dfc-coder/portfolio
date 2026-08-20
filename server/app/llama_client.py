from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatResult:
    content: str
    tool_calls: list[ToolCall]


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 90.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._slot = asyncio.Semaphore(1)

    def _payload(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.25,
            "max_tokens": 220,
            "parallel_tool_calls": False,
            "cache_prompt": True,
            "id_slot": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        async with self._slot:
            response = await self._client.post(
                f"{self._base_url}/v1/chat/completions",
                json=self._payload(messages, stream=False, tools=tools),
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            calls = []
            for item in message.get("tool_calls") or []:
                function = item.get("function", {})
                raw_arguments = function.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {}
                calls.append(
                    ToolCall(
                        id=item.get("id", "tool-call"),
                        name=function.get("name", ""),
                        arguments=arguments,
                    )
                )
            return ChatResult(content=message.get("content") or "", tool_calls=calls)

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        async with self._slot:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=self._payload(messages, stream=True, tools=None),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    payload = json.loads(data)
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content
