import copy
import json
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.prompt import build_messages
from app.tool_search import ToolSelection
from app.tools import TOOLS


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


class FakeToolSearch:
    def __init__(self, *tool_names: str) -> None:
        selected = [
            tool
            for tool in TOOLS
            if tool["function"]["name"] in tool_names
        ]
        self._selection = ToolSelection(
            tools=selected,
            scores={name: 1.0 for name in tool_names},
            latency_ms=0.0,
        )
        self.calls = []

    async def select(self, message, context):
        self.calls.append((message, copy.deepcopy(context)))
        return self._selection


def token_text(events) -> str:
    return "".join(
        str(payload["text"])
        for event, payload in events
        if event == "token"
    )


def returned_context(events):
    payloads = [payload for event, payload in events if event == "context"]
    assert len(payloads) == 1
    return payloads[0]["messages"]


def test_prompt_keeps_tool_mechanics_out_of_system_instructions() -> None:
    system = build_messages("Diego", [], "hola")[0]["content"]

    assert system.startswith("#Context#")
    assert "#Objective#" in system
    assert "#Response#" in system
    assert "#Examples#" in system
    assert "#Tool strategy#" not in system
    assert "search_portfolio" not in system
    assert "resolve_datetime" not in system
    assert "set_reminder_mock" not in system
    assert "<portfolio_subject>" in system
    assert "<name>Diego</name>" in system


@pytest.mark.asyncio
async def test_agent_streams_answer_and_flow_without_tool() -> None:
    chat = FakeChat([[chunk("Ho"), chunk("la."), chunk(finish_reason="stop")]])
    portfolio = FakePortfolio()
    agent = Agent(
        "Diego",
        chat,
        portfolio,
        model="qwen",
    )

    events = [event async for event in agent.respond("hola", [])]

    assert token_text(events) == "Hola."
    assert events[0] == ("status", {"phase": "model", "round": 1})
    assert ("status", {"phase": "responding", "round": 1}) in events
    assert portfolio.queries == []
    assert returned_context(events)[-1] == {"role": "assistant", "content": "Hola."}
    assert len(chat.chat.completions.requests) == 1
    assert chat.chat.completions.requests[0]["stream"] is True
    assert "tool_choice" not in chat.chat.completions.requests[0]


@pytest.mark.asyncio
async def test_agent_omits_tools_when_tool_search_returns_none() -> None:
    chat = FakeChat([[chunk("Hola."), chunk(finish_reason="stop")]])
    tool_search = FakeToolSearch()
    agent = Agent(
        "Diego",
        chat,
        FakePortfolio(),
        model="qwen",
        tool_search=tool_search,
    )

    events = [event async for event in agent.respond("hola", [])]

    assert token_text(events) == "Hola."
    request = chat.chat.completions.requests[0]
    assert "tools" not in request
    assert "parallel_tool_calls" not in request
    assert tool_search.calls == [("hola", [])]


@pytest.mark.asyncio
async def test_agent_rejects_tool_outside_selected_schemas() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-date",
                            name="resolve_datetime",
                            arguments='{"reference":"now","offset":0,"unit":"days"}',
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ]
        ]
    )
    agent = Agent(
        "Diego",
        chat,
        FakePortfolio(),
        model="qwen",
        tool_search=FakeToolSearch("search_portfolio"),
    )

    with pytest.raises(RuntimeError, match="ineligible tool: resolve_datetime"):
        _ = [event async for event in agent.respond("consulta", [])]

    request = chat.chat.completions.requests[0]
    assert [tool["function"]["name"] for tool in request["tools"]] == ["search_portfolio"]


@pytest.mark.asyncio
async def test_agent_preserves_streamed_tool_call_and_reports_flow() -> None:
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
    )

    events = [event async for event in agent.respond("¿Trabajó con Rust?", [])]

    assert token_text(events) == "El perfil incluye experiencia con Rust."
    assert portfolio.queries == ["Rust experience"]
    assert (
        "tool",
        {"name": "search_portfolio", "state": "running", "round": 1},
    ) in events
    assert (
        "tool",
        {"name": "search_portfolio", "state": "done", "ok": True, "round": 1},
    ) in events
    assert ("status", {"phase": "model", "round": 2}) in events

    second_messages = chat.chat.completions.requests[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["tool_calls"][0]["id"] == "call-search"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "call-search"
    assert json.loads(second_messages[-1]["content"])["ok"] is True

    context = returned_context(events)
    assert any(item.get("role") == "tool" for item in context)
    assert context[-1]["content"] == "El perfil incluye experiencia con Rust."


@pytest.mark.asyncio
async def test_agent_runs_generic_multi_round_tool_chain() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-resolve",
                            name="resolve_datetime",
                            arguments=json.dumps(
                                {
                                    "reference": "2026-09-04T19:00:00-03:00",
                                    "offset": 15,
                                    "unit": "days",
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
                                    "reference": "2026-09-19T19:00:00-03:00",
                                    "offset": 0,
                                    "unit": "minutes",
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
    )

    events = [
        event
        async for event in agent.respond(
            "Calculá 15 días después de 2026-09-04T19:00:00-03:00 y usá esa fecha para un recordatorio del CV",
            [],
        )
    ]

    assert token_text(events) == "Recordatorio simulado."
    assert len(chat.chat.completions.requests) == 3

    running_tools = [
        payload["name"]
        for event, payload in events
        if event == "tool" and payload["state"] == "running"
    ]
    assert running_tools == [
        "resolve_datetime",
        "set_reminder_mock",
    ]

    final_messages = chat.chat.completions.requests[-1]["messages"]
    tool_ids = [item["tool_call_id"] for item in final_messages if item["role"] == "tool"]
    assert tool_ids == ["call-resolve", "call-reminder"]


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
                            name="resolve_datetime",
                            arguments=json.dumps(
                                {
                                    "reference": "now",
                                    "offset": 0,
                                    "unit": "days",
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
    )

    events = [event async for event in agent.respond("consulta mixta", [])]

    assert token_text(events) == "Listo."
    second_messages = chat.chat.completions.requests[1]["messages"]
    assert [item["tool_call_id"] for item in second_messages[-2:]] == [
        "call-search",
        "call-date",
    ]


@pytest.mark.asyncio
async def test_agent_carries_tool_results_into_follow_up_turn() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-date",
                            name="resolve_datetime",
                            arguments=json.dumps(
                                {
                                    "reference": "2026-09-04T19:00:00-03:00",
                                    "offset": 15,
                                    "unit": "days",
                                }
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk("Sería el sábado 19 de septiembre de 2026."),
                chunk(finish_reason="stop"),
            ],
            [
                chunk("El sábado 19 de septiembre de 2026."),
                chunk(finish_reason="stop"),
            ],
        ]
    )
    agent = Agent(
        "Diego",
        chat,
        FakePortfolio(),
        model="qwen",
    )

    first_events = [
        event
        async for event in agent.respond("Dentro de 15 días, ¿qué día sería?", [])
    ]
    context = returned_context(first_events)

    second_events = [
        event async for event in agent.respond("¿Cuál sábado?", context)
    ]

    assert token_text(second_events) == "El sábado 19 de septiembre de 2026."
    follow_up_messages = chat.chat.completions.requests[-1]["messages"]
    prior_tool_messages = [item for item in follow_up_messages if item.get("role") == "tool"]
    assert len(prior_tool_messages) == 1
    prior_result = json.loads(prior_tool_messages[0]["content"])
    assert prior_result["result"]["date"] == "2026-09-19"
    assert prior_result["result"]["weekday_es"] == "sábado"
