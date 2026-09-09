import copy
from types import SimpleNamespace

import pytest

from app.dispatcher import Route
from app.prompt import PORTFOLIO_PROMPT
from app.tools import SEARCH_PORTFOLIO_SCHEMA
from app.worker import Worker, run_worker


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


async def _events(chat, portfolio, worker):
    return [
        event
        async for event in run_worker(
            "Diego",
            chat,
            portfolio,
            worker,
            "consulta",
            [],
            model="qwen",
            temperature=0.0,
            top_p=1.0,
            top_k=1,
            min_p=0.0,
            presence_penalty=0.0,
            repeat_penalty=1.0,
            max_tokens=256,
        )
    ]


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
            [_chunk(content='{"answer":"Respuesta final."}', finish_reason="stop")],
        ]
    )
    portfolio = _Portfolio()
    worker = Worker(Route.PORTFOLIO, PORTFOLIO_PROMPT, (SEARCH_PORTFOLIO_SCHEMA,))

    events = await _events(chat, portfolio, worker)

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
        if isinstance(payload, dict)
    )
