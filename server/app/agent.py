from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .prompt import build_messages

Profile = dict[str, Any]
Fact = tuple[str, str]

_QUERY_PREFIX = (
    "Instruct: Given a visitor question about a professional portfolio, retrieve profile "
    "passages containing the facts needed to answer it.\nQuery: "
)


class PortfolioAgent:
    def __init__(
        self,
        subject: str,
        profile: Profile,
        chat: AsyncOpenAI,
        embeddings: AsyncOpenAI,
        *,
        chat_model: str,
        embedding_model: str,
        temperature: float = 0.65,
        max_tokens: int = 180,
        max_chars: int = 4000,
        max_documents: int = 4,
        min_score: float = 0.10,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._embeddings = embeddings
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._min_score = min_score
        self._documents = self._build_documents(profile)
        self._vectors: list[list[float]] | None = None

    async def warm(self) -> None:
        if self._vectors is None:
            self._vectors = await self._embed([text for _, text in self._documents])

    async def respond(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        query = "\n".join(
            [
                *(
                    item["content"]
                    for item in history[-6:]
                    if item["role"] == "user"
                ),
                message,
            ]
        )[-2000:]
        evidence = await self._search(query)
        messages = build_messages(self._subject, history[-6:], message, evidence)

        stream = await self._chat.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )

        emitted = False
        async for chunk in stream:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content or ""
            if text:
                emitted = True
                yield text

        if not emitted:
            raise RuntimeError("LLM returned an empty response")

    async def _search(self, query: str) -> list[Fact]:
        await self.warm()
        assert self._vectors is not None
        query_vector = (await self._embed([f"{_QUERY_PREFIX}{query.strip()}"]))[0]
        ranked = sorted(
            (
                (self._cosine(query_vector, vector), source, text)
                for (source, text), vector in zip(self._documents, self._vectors, strict=True)
            ),
            reverse=True,
        )

        facts: list[Fact] = []
        chars = 0
        for score, source, text in ranked:
            if score < self._min_score or len(facts) >= self._max_documents:
                break
            if facts and chars + len(text) > self._max_chars:
                break
            facts.append((source, text))
            chars += len(text)
        return facts

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._embeddings.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    @staticmethod
    def _build_documents(profile: Profile) -> list[Fact]:
        documents: list[Fact] = []
        for section, value in profile.items():
            if isinstance(value, list):
                documents.extend(
                    (f"{section}.{index}", json.dumps(item, ensure_ascii=False))
                    for index, item in enumerate(value)
                )
            else:
                documents.append((section, json.dumps(value, ensure_ascii=False)))
        return documents

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
