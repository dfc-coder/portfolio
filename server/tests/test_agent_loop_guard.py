import copy
from types import SimpleNamespace

import pytest

from app.agent import Agent


def _chunk(*, tool_calls=None, content=None, finish_reason=None):
    calls = []
    for index, tool_call in enumerate(tool_calls or []):
        calls.append(
            SimpleNamespace(
                index=index,
                id=tool_call.get("id"),
                function=SimpleNamespace(
                    name=tool_call.get("name"),
                    arguments=tool_call.get("arguments"),
                ),
            )
        )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                index=0,
                delta=SimpleNamespace(
                    role="assistant",
                    content=content,
                    tool_calls=calls,
                    reasoning_content=None,
                ),
                finish_reason=finish_reason,
            )
        ]
    )


class _Stream:
    def __init__(self, chunks):
        self._chunks = chunks

    async def __aiter__(self):
        for item in self._chunks:
            yield item


class _Completions:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return _Stream(next(self._responses))


class _Chat:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_Completions(responses))


class _Portfolio:
    def __init__(self):
        self.queries = []

    async def search(self, query):
        self.queries.append(query)
        return [{"source": "profile", "text": "Rust"}]


@pytest.mark.asyncio
async def test_repeated_successful_tool_call_is_reused_then_tools_are_removed() -> None:
    first = {
        "id": "call-1",
        "name": "search_portfolio",
        "arguments": '{"query":"Rust"}',
    }
    repeated = {
        "id": "call-2",
        "name": "search_portfolio",
        "arguments": '{"query":"Rust"}',
    }
    chat = _Chat(
        [
            [_chunk(tool_calls=[first], finish_reason="tool_calls")],
            [_chunk(tool_calls=[repeated], finish_reason="tool_calls")],
            [_chunk(content="Respuesta final.", finish_reason="stop")],
        ]
    )
    portfolio = _Portfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("consulta", [])]

    assert portfolio.queries == ["Rust"]
    assert len(chat.chat.completions.requests) == 3
    assert "tools" in chat.chat.completions.requests[0]
    assert "tools" in chat.chat.completions.requests[1]
    assert "tools" not in chat.chat.completions.requests[2]
    assert any(
        event == "tool"
        and payload.get("name") == "search_portfolio"
        and payload.get("reused") is True
        for event, payload in events
    )


@pytest.mark.asyncio
async def test_repeated_call_plus_new_call_executes_only_the_new_call() -> None:
    search = {
        "id": "call-search-1",
        "name": "search_portfolio",
        "arguments": '{"query":"Rust"}',
    }
    repeated_search = {
        "id": "call-search-2",
        "name": "search_portfolio",
        "arguments": '{"query":"Rust"}',
    }
    new_date = {
        "id": "call-date",
        "name": "resolve_datetime",
        "arguments": '{"reference":"2026-09-09","offset":0,"unit":"days"}',
    }
    chat = _Chat(
        [
            [_chunk(tool_calls=[search], finish_reason="tool_calls")],
            [
                _chunk(
                    tool_calls=[repeated_search, new_date],
                    finish_reason="tool_calls",
                )
            ],
            [_chunk(content="Listo.", finish_reason="stop")],
        ]
    )
    portfolio = _Portfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("consulta", [])]

    assert portfolio.queries == ["Rust"]

    running = [
        payload["name"]
        for event, payload in events
        if event == "tool" and payload.get("state") == "running"
    ]
    assert running == ["search_portfolio", "resolve_datetime"]

    reused = [
        payload["name"]
        for event, payload in events
        if event == "tool" and payload.get("reused") is True
    ]
    assert reused == ["search_portfolio"]
