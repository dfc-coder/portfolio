from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float = 0.65
    max_tokens: int = 180
    top_p: float = 0.9
    top_k: int = 20


class LlamaCpp:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 90.0,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._slot = asyncio.Semaphore(1)

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def stream(
        self,
        messages: list[dict[str, str]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "cache_prompt": True,
            "id_slot": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        async with self._slot:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    body = json.loads(data)
                    if not isinstance(body, Mapping):
                        continue
                    for choice in body.get("choices") or []:
                        if not isinstance(choice, Mapping):
                            continue
                        delta = choice.get("delta")
                        if not isinstance(delta, Mapping):
                            continue
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield content
