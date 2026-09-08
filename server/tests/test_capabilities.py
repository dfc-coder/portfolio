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
            if "Hola" in query:
                vectors = [[1.0, 0.0, 0.0, 0.0]]
            elif "Rust" in query or "Go?" in query:
                vectors = [[0.0, 1.0, 0.0, 0.0]]
            elif "Recordame" in query:
                vectors = [[0.0, 0.0, 0.0, 1.0]]
            else:
                vectors = [[0.0, 0.0, 1.0, 0.0]]

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
async def test_semantic_selector_returns_portfolio_tool_for_professional_question() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("¿Diego trabajó con Rust?", [])

    assert decision.route == "portfolio"
    assert decision.names == ("portfolio",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_semantic_selector_returns_datetime_tool_for_date_request() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("¿Qué fecha será mañana?", [])

    assert decision.route == "datetime"
    assert decision.names == ("datetime",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_semantic_selector_returns_only_reminder_tool_for_reminder_request() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("Recordame esto mañana", [])

    assert decision.route == "reminder"
    assert decision.names == ("reminder",)
    assert decision.requires_tool is True


@pytest.mark.asyncio
async def test_read_only_followup_keeps_tool_available_without_forcing_it() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")
    context = [
        {"role": "user", "content": "Dentro de 15 días, ¿qué día sería?"},
        {"role": "assistant", "content": "Sería el sábado 19 de septiembre de 2026."},
    ]

    decision = await selector.select("¿Cuál sábado?", context)

    assert decision.route == "datetime"
    assert decision.names == ("datetime",)
    assert decision.requires_tool is False


@pytest.mark.asyncio
async def test_reminder_action_stays_required_with_existing_context() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")
    context = [{"role": "assistant", "content": "Hablábamos de otra cosa."}]

    decision = await selector.select("Recordame esto mañana", context)

    assert decision.route == "reminder"
    assert decision.names == ("reminder",)
    assert decision.requires_tool is True


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
