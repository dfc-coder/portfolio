import copy
from types import SimpleNamespace

import pytest

from app.agent import Agent, MAX_TOOL_ROUNDS
from app.tools import TOOL_SCHEMAS


def tool_delta(
    index: int,
    *,
    call_id: str | None = None,
    name: str | None = None,
    arguments: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def chunk(
    content: str | None = None,
    *,
    tool_calls=None,
    finish_reason: str | None = None,
    reasoning_content: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                index=0,
                delta=SimpleNamespace(
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    reasoning_content=reasoning_content,
                ),
                finish_reason=finish_reason,
            )
        ]
    )


class FakeStream:
    def __init__(self, chunks) -> None:
        self._chunks = chunks

    async def __aiter__(self):
        for item in self._chunks:
            yield item


class FakeCompletions:
    def __init__(self, responses) -> None:
        self._responses = iter(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return FakeStream(next(self._responses))


class FakeChat:
    def __init__(self, responses) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class FakePortfolio:
    def __init__(self) -> None:
        self.queries = []

    async def search(self, query: str):
        self.queries.append(query)
        return [{"source": "projects.0", "text": "Rust"}]


def token_payloads(events) -> list[str]:
    return [
        str(payload["text"])
        for event, payload in events
        if event == "token"
    ]


@pytest.mark.asyncio
async def test_direct_answer_streams_token_by_token_without_tool() -> None:
    chat = FakeChat(
        [[chunk("Hola"), chunk(" mundo"), chunk(finish_reason="stop")]]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("Hola", [])]

    assert token_payloads(events) == ["Hola", " mundo"]
    assert portfolio.queries == []
    assert len(chat.chat.completions.requests) == 1
    request = chat.chat.completions.requests[0]
    assert request["stream"] is True
    assert request["parallel_tool_calls"] is False
    assert request["tools"] == list(TOOL_SCHEMAS)


@pytest.mark.asyncio
async def test_tool_round_uses_original_user_message_for_portfolio() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-1",
                            name="search_portfolio",
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("Diego "), chunk("usa Rust."), chunk(finish_reason="stop")],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("¿Diego usa Rust?", [])]

    assert token_payloads(events) == ["Diego ", "usa Rust."]
    assert portfolio.queries == ["¿Diego usa Rust?"]
    second_messages = chat.chat.completions.requests[1]["messages"]
    assert second_messages[-2]["tool_calls"][0]["id"] == "call-1"
    assert second_messages[-2]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "call-1"


@pytest.mark.asyncio
async def test_fragmented_tool_call_is_reconstructed() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-",
                            name="search_",
                            arguments="{",
                        )
                    ]
                ),
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="1",
                            name="portfolio",
                            arguments="}",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
            ],
            [chunk("ok"), chunk(finish_reason="stop")],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("consulta", [])]

    assert token_payloads(events) == ["ok"]
    assert portfolio.queries == ["consulta"]


@pytest.mark.asyncio
async def test_reasoning_content_is_never_streamed() -> None:
    chat = FakeChat(
        [[
            chunk(reasoning_content="private reasoning"),
            chunk("visible"),
            chunk(finish_reason="stop"),
        ]]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [])]

    assert token_payloads(events) == ["visible"]


@pytest.mark.asyncio
async def test_mixed_text_and_tool_call_fails_protocol() -> None:
    chat = FakeChat(
        [[
            chunk("partial"),
            chunk(
                tool_calls=[
                    tool_delta(
                        0,
                        call_id="call-1",
                        name="search_portfolio",
                        arguments="{}",
                    )
                ]
            ),
        ]]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    with pytest.raises(RuntimeError, match="mixed final text with tool calls"):
        [event async for event in agent.respond("consulta", [])]


@pytest.mark.asyncio
async def test_tool_loop_is_bounded() -> None:
    response = [
        chunk(
            tool_calls=[
                tool_delta(
                    0,
                    call_id="call-x",
                    name="search_portfolio",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
        )
    ]
    chat = FakeChat([response for _ in range(MAX_TOOL_ROUNDS + 1)])
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    with pytest.raises(RuntimeError, match="tool loop limit reached"):
        [event async for event in agent.respond("consulta", [])]


@pytest.mark.asyncio
async def test_context_is_sent_and_returned() -> None:
    context = [
        {"role": "user", "content": "antes"},
        {"role": "assistant", "content": "previo"},
    ]
    chat = FakeChat([[chunk("nuevo"), chunk(finish_reason="stop")]])
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("ahora", context)]

    request_messages = chat.chat.completions.requests[0]["messages"]
    assert request_messages[1:3] == context
    returned = next(payload["messages"] for event, payload in events if event == "context")
    assert returned[-2:] == [
        {"role": "user", "content": "ahora"},
        {"role": "assistant", "content": "nuevo"},
    ]


@pytest.mark.asyncio
async def test_diagnostics_records_zero_argument_portfolio_tool() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-1",
                            name="search_portfolio",
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("final"), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [], diagnostics=True)]

    trace = next(payload for event, payload in events if event == "trace")
    assert trace["status"] == "ok"
    assert trace["rounds"][0]["tool_calls"][0]["name"] == "search_portfolio"
    assert trace["rounds"][0]["tool_calls"][0]["arguments"] == {}
    assert trace["output"] == "final"


@pytest.mark.asyncio
async def test_fake_resolve_datetime_executes_requested_tool() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="date-1",
                            name="resolve_datetime",
                            arguments=(
                                '{"reference":"2026-12-25","offset":0,"unit":"days"}'
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("viernes"), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [], diagnostics=True)]

    trace = next(payload for event, payload in events if event == "trace")
    call = trace["rounds"][0]["tool_calls"][0]
    assert call["name"] == "resolve_datetime"
    assert call["ok"] is True
    assert call["result"]["result"]["date"] == "2026-12-25"


@pytest.mark.asyncio
async def test_fake_reminder_executes_requested_tool() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="rem-1",
                            name="set_reminder_mock",
                            arguments=(
                                '{"reference":"2026-12-01T10:30:00-03:00",'
                                '"offset":0,"unit":"minutes","message":"Enviar propuesta"}'
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("simulado"), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [], diagnostics=True)]

    trace = next(payload for event, payload in events if event == "trace")
    call = trace["rounds"][0]["tool_calls"][0]
    assert call["name"] == "set_reminder_mock"
    assert call["ok"] is True
    assert call["result"]["result"]["status"] == "simulated_only"


@pytest.mark.asyncio
async def test_trace_records_final_ttft() -> None:
    chat = FakeChat([[chunk("hola"), chunk(finish_reason="stop")]])
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [], diagnostics=True)]

    trace = next(payload for event, payload in events if event == "trace")
    assert isinstance(trace["final_ttft_ms"], float)
    assert trace["final_ttft_ms"] >= 0
    assert trace["duration_ms"] >= trace["final_ttft_ms"]
