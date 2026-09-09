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
            if "MIXED" in query:
                vectors = [[0.1, 0.70, 0.68, 0.1]]
            elif "AMBIGUOUS_PORTFOLIO" in query:
                vectors = [[0.72, 0.70, 0.1, 0.1]]
            elif "REMINDER" in query:
                vectors = [[0.1, 0.1, 0.1, 1.0]]
            elif "PORTFOLIO" in query or "Go?" in query:
                vectors = [[0.1, 1.0, 0.1, 0.1]]
            elif "DATETIME" in query:
                vectors = [[0.1, 0.1, 1.0, 0.1]]
            else:
                vectors = [[1.0, 0.1, 0.1, 0.1]]

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
async def test_clear_conversation_returns_no_candidate_tools() -> None:
    embeddings = FakeEmbeddingsClient()
    selector = SemanticCapabilitySelector(embeddings, model="embedding")

    decision = await selector.select("Hola", [])

    assert decision.route == "conversation"
    assert decision.names == ()
    assert decision.requires_tool is False
    assert len(embeddings.embeddings.requests) == 2


@pytest.mark.asyncio
async def test_close_portfolio_match_is_kept_as_candidate() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("AMBIGUOUS_PORTFOLIO", [])

    assert decision.route == "portfolio"
    assert decision.names == ("portfolio",)
    assert decision.requires_tool is False


@pytest.mark.asyncio
async def test_strong_reminder_returns_only_reminder_candidate() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("REMINDER", [])

    assert decision.route == "reminder"
    assert decision.names == ("reminder",)
    assert decision.requires_tool is False


@pytest.mark.asyncio
async def test_mixed_request_can_return_two_candidate_tools() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")

    decision = await selector.select("MIXED", [])

    assert decision.route == "portfolio+datetime"
    assert decision.names == ("portfolio", "datetime")
    assert decision.requires_tool is False


@pytest.mark.asyncio
async def test_context_does_not_force_candidate_execution() -> None:
    selector = SemanticCapabilitySelector(FakeEmbeddingsClient(), model="embedding")
    context = [
        {"role": "user", "content": "¿Diego usa Rust?"},
        {"role": "assistant", "content": "Sí."},
    ]

    decision = await selector.select("¿Y Go?", context)

    assert decision.names == ("portfolio",)
    assert decision.requires_tool is False


@pytest.mark.asyncio
async def test_semantic_selector_warms_route_vectors_once() -> None:
    embeddings = FakeEmbeddingsClient()
    selector = SemanticCapabilitySelector(embeddings, model="embedding")

    await selector.warm()
    await selector.select("Hola", [])
    await selector.select("PORTFOLIO", [])

    route_embedding_requests = [
        request
        for request in embeddings.embeddings.requests
        if len(request["input"]) == 4
    ]
    assert len(route_embedding_requests) == 1
