import copy
from types import SimpleNamespace

import pytest

from app.agent import Agent


def _chunk(*, tool_call=None, content=None, finish_reason=None):
    calls = []
    if tool_call is not None:
        calls = [
            SimpleNamespace(
                index=0,
                id=tool_call.get("id"),
                function=SimpleNamespace(
                    name=tool_call.get("name"),
                    arguments=tool_call.get("arguments"),
                ),
            )
        ]
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=calls),
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
async def test_repeated_successful_tool_call_is_reused_once_then_tools_are_removed() -> None:
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
            [_chunk(tool_call=first, finish_reason="tool_calls")],
            [_chunk(tool_call=repeated, finish_reason="tool_calls")],
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
        event == "token" and payload.get("text") == "Respuesta final."
        for event, payload in events
    )
