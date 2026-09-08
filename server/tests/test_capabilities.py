from types import SimpleNamespace

import pytest

from app.capabilities import SemanticCapabilitySelector


class FakeEmbeddingsEndpoint:
    def __init__(self) -> None:
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        texts = kwargs["input"]

        if len(texts) == 3:
            vectors = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        else:
            query = texts[0]
            if "Hola" in query:
                vectors = [[1.0, 0.0, 0.0]]
            elif "Rust" in query:
                vectors = [[0.0, 1.0, 0.0]]
            else:
                vectors = [[0.0, 0.0, 1.0]]

        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=vector)
                for index, vector in enumerate(vectors)
            ]
        )


class FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsEndpoint()


@pytest.mark.asyncio
async def test_semantic_selector_returns_no_tools_for_general_conversation() -> None:
    embeddings = FakeEmbeddingsClient()
    selector = SemanticCapabilitySelector(embeddings, model="embedding")

    decision = await selector.select("Hola", [])

    assert decision.route == "conversation"
    assert decision.names == ()
    assert len(embeddings.embeddings.requests) == 2


@pytest.mark.asyncio
async def test_semantic_selector_returns_portfolio_tool_for_professional_question() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("¿Diego trabajó con Rust?", [])

    assert decision.route == "portfolio"
    assert decision.names == ("portfolio",)


@pytest.mark.asyncio
async def test_semantic_selector_returns_temporal_tools_for_date_or_reminder_request() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("Recordame esto mañana", [])

    assert decision.route == "temporal"
    assert decision.names == ("datetime", "reminder")


@pytest.mark.asyncio
async def test_semantic_selector_warms_route_vectors_once() -> None:
    embeddings = FakeEmbeddingsClient()
    selector = SemanticCapabilitySelector(embeddings, model="embedding")

    await selector.warm()
    await selector.select("Hola", [])
    await selector.select("¿Diego trabajó con Rust?", [])

    route_embedding_requests = [
        request
        for request in embeddings.embeddings.requests
        if len(request["input"]) == 3
    ]
    assert len(route_embedding_requests) == 1
