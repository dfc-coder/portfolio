from __future__ import annotations

import asyncio

import httpx

_RETRIEVAL_INSTRUCTION = (
    "Given a visitor question about a professional portfolio or CV, retrieve the profile "
    "passages containing the facts needed to answer it."
)


class Embeddings:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._slot = asyncio.Semaphore(1)

    async def documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def query(self, text: str) -> list[float]:
        value = f"Instruct: {_RETRIEVAL_INSTRUCTION}\nQuery: {text.strip()}"
        return (await self._embed([value]))[0]

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with self._slot:
            response = await self._client.post(
                f"{self._base_url}/v1/embeddings",
                json={"model": self._model, "input": texts, "encoding_format": "float"},
            )
        response.raise_for_status()
        data = sorted(response.json().get("data") or [], key=lambda item: int(item["index"]))
        if len(data) != len(texts):
            raise ValueError("embedding service returned an unexpected vector count")
        return [[float(value) for value in item["embedding"]] for item in data]
