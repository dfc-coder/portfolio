from __future__ import annotations

import asyncio

import httpx


class LlamaCppReranker:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._slot = asyncio.Semaphore(1)

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []

        async with self._slot:
            response = await self._client.post(
                f"{self._base_url}/v1/rerank",
                json={
                    "model": self._model,
                    "query": query,
                    "documents": documents,
                    "top_n": len(documents),
                },
            )
            response.raise_for_status()
            payload = response.json()

        scores = [0.0] * len(documents)
        seen: set[int] = set()
        for item in payload.get("results") or []:
            index = int(item["index"])
            if index < 0 or index >= len(documents):
                raise ValueError(f"Reranker returned invalid document index: {index}")
            scores[index] = float(item["relevance_score"])
            seen.add(index)

        if len(seen) != len(documents):
            raise ValueError("Reranker did not return a score for every route candidate.")
        return scores

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
