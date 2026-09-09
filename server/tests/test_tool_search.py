import pytest

from app.tool_search import ToolSearch, tool_name, tool_search_text
from app.tools import TOOLS


class FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.calls = []

    async def rank(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, documents))
        return list(self._scores)


@pytest.mark.asyncio
async def test_tool_search_can_return_no_tools() -> None:
    reranker = FakeReranker([0.1, 0.2, 0.3])
    search = ToolSearch(reranker)

    selection = await search.select("Hola", [])

    assert selection.tools == []
    assert selection.scores == {
        "search_portfolio": 0.1,
        "resolve_datetime": 0.2,
        "set_reminder_mock": 0.3,
    }


@pytest.mark.asyncio
async def test_tool_search_can_return_one_tool() -> None:
    reranker = FakeReranker([0.91, 0.03, 0.02])
    search = ToolSearch(reranker)

    selection = await search.select("¿Diego usa Rust?", [])

    assert [tool_name(tool) for tool in selection.tools] == ["search_portfolio"]


@pytest.mark.asyncio
async def test_tool_search_can_return_multiple_tools() -> None:
    reranker = FakeReranker([0.93, 0.88, 0.02])
    search = ToolSearch(reranker)

    selection = await search.select("¿Qué stack usa PocketTrace y qué fecha es hoy?", [])

    assert [tool_name(tool) for tool in selection.tools] == [
        "search_portfolio",
        "resolve_datetime",
    ]


@pytest.mark.asyncio
async def test_tool_search_uses_recent_context_for_followups() -> None:
    reranker = FakeReranker([0.9, 0.1, 0.1])
    search = ToolSearch(reranker)
    context = [
        {"role": "user", "content": "¿Diego usa Rust?"},
        {"role": "assistant", "content": "Sí."},
    ]

    await search.select("¿Y Go?", context)

    query, _ = reranker.calls[0]
    assert "Recent context:" in query
    assert "¿Diego usa Rust?" in query
    assert "Current visitor request:" in query
    assert "¿Y Go?" in query


def test_tool_search_text_is_derived_from_schema() -> None:
    text = tool_search_text(TOOLS[0])

    assert "Tool: search_portfolio" in text
    assert TOOLS[0]["function"]["description"] in text
    assert TOOLS[0]["function"]["parameters"]["properties"]["query"]["description"] in text


@pytest.mark.asyncio
async def test_tool_search_rejects_wrong_score_count() -> None:
    search = ToolSearch(FakeReranker([0.9]))

    with pytest.raises(ValueError, match="score count"):
        await search.select("consulta", [])
