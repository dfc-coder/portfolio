from __future__ import annotations

import httpx


class LlamaCppEmbeddingClient:
    """OpenAI-compatible embedding client backed by llama.cpp."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        *,
        query_instruction: str = "Retrieve the text that best matches the visitor's intent.",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._query_instruction = query_instruction
        self._client = client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        query = f"Instruct: {self._query_instruction}\nQuery: {text.strip()}"
        vectors = await self._embed([query])
        return vectors[0]

    async def health(self) -> bool:
        try:
            if self._client is not None:
                response = await self._client.get(f"{self._base_url}/health", timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self._base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self._model,
            "input": texts,
            "encoding_format": "float",
        }
        if self._client is not None:
            response = await self._client.post(
                f"{self._base_url}/v1/embeddings",
                json=payload,
                timeout=self._timeout_seconds,
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/v1/embeddings",
                    json=payload,
                )
        response.raise_for_status()
        data = response.json().get("data") or []
        ordered = sorted(data, key=lambda item: int(item["index"]))
        if len(ordered) != len(texts):
            raise ValueError("Embedding service returned an unexpected vector count")
        return [[float(value) for value in item["embedding"]] for item in ordered]
