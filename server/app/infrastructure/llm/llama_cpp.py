from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import BaseModel

from app.ports.llm import GenerationConfig


class LlamaCppClient:
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
        config: GenerationConfig,
        *,
        stream: bool,
        response_schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "cache_prompt": True,
            "id_slot": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if config.top_p is not None:
            payload["top_p"] = config.top_p
        if config.top_k is not None:
            payload["top_k"] = config.top_k
        if config.presence_penalty is not None:
            payload["presence_penalty"] = config.presence_penalty
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            }
        return payload

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        async with self._slot:
            payload = self._payload(
                messages,
                config,
                stream=False,
                response_schema=response_schema,
            )
            response = await self._client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            )
            if response.status_code in {400, 422} and response_schema is not None:
                fallback = dict(payload)
                fallback["response_format"] = {"type": "json_object"}
                response = await self._client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=fallback,
                )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            return message.get("content") or ""

    async def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        async with self._slot:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=self._payload(messages, config, stream=True),
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
