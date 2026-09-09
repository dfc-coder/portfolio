from __future__ import annotations

from typing import Any

import httpx


class Reranker:
    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http = httpx.AsyncClient(timeout=timeout_seconds)

    async def rank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []

        response = await self._http.post(
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
        return _scores(payload, len(documents))

    async def close(self) -> None:
        await self._http.aclose()


def _scores(payload: dict[str, Any], count: int) -> list[float]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("reranker response is missing results")

    scores: list[float | None] = [None] * count
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("reranker result must be an object")
        index = item.get("index")
        score = item.get("relevance_score")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count:
            raise ValueError("reranker result has an invalid index")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("reranker result has an invalid relevance_score")
        if scores[index] is not None:
            raise ValueError("reranker returned a duplicate index")
        scores[index] = float(score)

    if any(score is None for score in scores):
        raise ValueError("reranker did not score every document")
    return [float(score) for score in scores]
