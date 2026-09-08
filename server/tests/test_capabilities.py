from types import SimpleNamespace

import pytest

from app.capabilities import SemanticCapabilitySelector


class FakeEmbeddingsEndpoint:
    def __init__(self) -> None:
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        texts = kwargs["input"]

        if len(texts) == 4:
            vectors = [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        else:
            query = texts[0]
            if "Recordame" in query:
                vectors = [[0.0, 0.0, 0.0, 1.0]]
            elif "fecha" in query or "mañana" in query:
                vectors = [[0.0, 0.0, 1.0, 0.0]]
            elif "Rust" in query or "Go" in query:
                vectors = [[0.0, 1.0, 0.0, 0.0]]
            else:
                vectors = [[1.0, 0.0, 0.0, 0.0]]

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
    assert decision.requires_tool is False
    assert len(embeddings.embeddings.requests) == 2


@pytest.mark.asyncio
async def test_semantic_selector_returns_only_portfolio_for_professional_question() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("¿Diego trabajó con Rust?", [])

    assert decision.route == "portfolio"
    assert decision.names == ("portfolio",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_semantic_selector_returns_only_datetime_for_date_question() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("¿Qué fecha será mañana?", [])

    assert decision.route == "datetime"
    assert decision.names == ("datetime",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_semantic_selector_returns_only_reminder_for_action_request() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("Recordame en 30 minutos revisar el portfolio", [])

    assert decision.route == "reminder"
    assert decision.names == ("reminder",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_semantic_selector_uses_recent_context_for_abbreviated_followup() -> None:
    embeddings = FakeEmbeddingsClient()
    selector = SemanticCapabilitySelector(embeddings, model="embedding")

    decision = await selector.select(
        "¿Y Go?",
        [
            {"role": "user", "content": "¿Diego trabajó con Rust?"},
            {"role": "assistant", "content": "Sí."},
        ],
    )

    assert decision.route == "portfolio"
    query = embeddings.embeddings.requests[-1]["input"][0]
    assert "Recent conversation:" in query
    assert "¿Diego trabajó con Rust?" in query
    assert "Current visitor message:" in query
    assert "¿Y Go?" in query


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
        if len(request["input"]) == 4
    ]
    assert len(route_embedding_requests) == 1
