import pytest

from app.tool_search import ToolSearch, tool_name, tool_search_text
from app.tools import TOOLS


class FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.calls = []

    async def rank(
        self,
        query: str,
        documents: list[str],
        *,
        instruction: str | None = None,
    ) -> list[float]:
        self.calls.append((query, documents, instruction))
        return list(self._scores)


@pytest.mark.asyncio
async def test_tool_search_can_return_no_tools() -> None:
    reranker = FakeReranker([0.9, 0.1, 0.2, 0.3])
    search = ToolSearch(reranker)

    selection = await search.select("Hola", [])

    assert selection.tools == []
    assert selection.scores == {
        "direct_response": 0.9,
        "search_portfolio": 0.1,
        "resolve_datetime": 0.2,
        "set_reminder_mock": 0.3,
    }


@pytest.mark.asyncio
async def test_tool_search_can_return_one_tool() -> None:
    reranker = FakeReranker([0.1, 0.91, 0.03, 0.02])
    search = ToolSearch(reranker)

    selection = await search.select("¿Diego usa Rust?", [])

    assert [tool_name(tool) for tool in selection.tools] == ["search_portfolio"]


@pytest.mark.asyncio
async def test_tool_search_can_return_multiple_tools() -> None:
    reranker = FakeReranker([0.1, 0.93, 0.88, 0.02])
    search = ToolSearch(reranker)

    selection = await search.select("¿Qué stack usa PocketTrace y qué fecha es hoy?", [])

    assert [tool_name(tool) for tool in selection.tools] == [
        "search_portfolio",
        "resolve_datetime",
    ]


@pytest.mark.asyncio
async def test_direct_response_suppresses_related_but_unneeded_tool() -> None:
    reranker = FakeReranker([0.99, 0.98, 0.01, 0.01])
    search = ToolSearch(reranker)

    selection = await search.select("¿Para qué sirve este portfolio?", [])

    assert selection.tools == []


@pytest.mark.asyncio
async def test_tool_must_beat_direct_response() -> None:
    reranker = FakeReranker([0.8, 0.8, 0.1, 0.1])
    search = ToolSearch(reranker)

    selection = await search.select("consulta ambigua", [])

    assert selection.tools == []


@pytest.mark.asyncio
async def test_tool_search_uses_recent_context_for_followups() -> None:
    reranker = FakeReranker([0.1, 0.9, 0.1, 0.1])
    search = ToolSearch(reranker)
    context = [
        {"role": "user", "content": "¿Diego usa Rust?"},
        {"role": "assistant", "content": "Sí."},
    ]

    await search.select("¿Y Go?", context)

    query, _, instruction = reranker.calls[0]
    assert "Recent context:" in query
    assert "¿Diego usa Rust?" in query
    assert "Current visitor request:" in query
    assert "¿Y Go?" in query
    assert instruction is not None
    assert "required to satisfy" in instruction


def test_tool_search_text_is_derived_from_schema() -> None:
    text = tool_search_text(TOOLS[0])

    assert "Tool: search_portfolio" in text
    assert TOOLS[0]["function"]["description"] in text
    assert TOOLS[0]["function"]["parameters"]["properties"]["query"]["description"] in text


@pytest.mark.asyncio
async def test_tool_search_rejects_wrong_score_count() -> None:
    search = ToolSearch(FakeReranker([0.9]))

    with pytest.raises(ValueError, match="candidate count"):
        await search.select("consulta", [])
