import copy
import json
from types import SimpleNamespace

import pytest

from app.agent import Agent


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
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
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
        return [{"source": "projects.0", "text": '{"stack":["Rust"]}'}]


@pytest.mark.asyncio
async def test_agent_streams_answer_without_tool() -> None:
    chat = FakeChat([[chunk("Ho"), chunk("la."), chunk(finish_reason="stop")]])
    portfolio = FakePortfolio()
    agent = Agent(
        "Diego",
        chat,
        portfolio,
        model="qwen",
        timezone="America/Argentina/Buenos_Aires",
    )

    parts = [part async for part in agent.respond("hola", [])]

    assert parts == ["Ho", "la."]
    assert portfolio.queries == []
    assert len(chat.chat.completions.requests) == 1
    assert chat.chat.completions.requests[0]["stream"] is True


@pytest.mark.asyncio
async def test_agent_preserves_streamed_tool_call_and_result_messages() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-search",
                            name="search_portfolio",
                            arguments='{"query":"Rust',
                        )
                    ]
                ),
                chunk(
                    tool_calls=[tool_delta(0, arguments=' experience"}')],
                    finish_reason="tool_calls",
                ),
            ],
            [
                chunk("El perfil incluye "),
                chunk("experiencia con Rust."),
                chunk(finish_reason="stop"),
            ],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent(
        "Diego",
        chat,
        portfolio,
        model="qwen",
        timezone="America/Argentina/Buenos_Aires",
    )

    response = "".join([part async for part in agent.respond("¿Trabajó con Rust?", [])])

    assert response == "El perfil incluye experiencia con Rust."
    assert portfolio.queries == ["Rust experience"]

    second_messages = chat.chat.completions.requests[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["tool_calls"][0]["id"] == "call-search"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "call-search"
    assert json.loads(second_messages[-1]["content"])["ok"] is True


@pytest.mark.asyncio
async def test_agent_runs_multi_round_tool_chain() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-now",
                            name="get_current_datetime",
                            arguments="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-add",
                            name="add_duration_to_datetime",
                            arguments=json.dumps(
                                {
                                    "datetime": "2030-01-01T10:00:00-03:00",
                                    "days": 30,
                                }
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-reminder",
                            name="set_reminder_mock",
                            arguments=json.dumps(
                                {
                                    "datetime": "2030-01-31T10:00:00-03:00",
                                    "message": "Revisar el CV",
                                }
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("Recordatorio simulado."), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent(
        "Diego",
        chat,
        FakePortfolio(),
        model="qwen",
        timezone="America/Argentina/Buenos_Aires",
    )

    response = "".join(
        [part async for part in agent.respond("Recordame en 30 días revisar el CV", [])]
    )

    assert response == "Recordatorio simulado."
    assert len(chat.chat.completions.requests) == 4

    final_messages = chat.chat.completions.requests[-1]["messages"]
    tool_ids = [item["tool_call_id"] for item in final_messages if item["role"] == "tool"]
    assert tool_ids == ["call-now", "call-add", "call-reminder"]


@pytest.mark.asyncio
async def test_agent_returns_multiple_tool_results_in_one_round() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-search",
                            name="search_portfolio",
                            arguments='{"query":"Rust"}',
                        ),
                        tool_delta(
                            1,
                            call_id="call-date",
                            name="add_duration_to_datetime",
                            arguments=json.dumps(
                                {
                                    "datetime": "2030-01-01T10:00:00-03:00",
                                    "days": 1,
                                }
                            ),
                        ),
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [chunk("Listo."), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent(
        "Diego",
        chat,
        FakePortfolio(),
        model="qwen",
        timezone="America/Argentina/Buenos_Aires",
    )

    response = "".join([part async for part in agent.respond("consulta mixta", [])])

    assert response == "Listo."
    second_messages = chat.chat.completions.requests[1]["messages"]
    assert [item["tool_call_id"] for item in second_messages[-2:]] == [
        "call-search",
        "call-date",
    ]
