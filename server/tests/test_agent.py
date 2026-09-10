import copy
import json
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.tools import (
    RESOLVE_DATETIME_SCHEMA,
    SEARCH_PORTFOLIO_SCHEMA,
    SET_REMINDER_MOCK_SCHEMA,
)


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
                index=0,
                delta=SimpleNamespace(
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    reasoning_content=None,
                ),
                finish_reason=finish_reason,
            )
        ]
    )


def classifier_response(routes: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps({"routes": routes}),
                )
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
        response = next(self._responses)
        if isinstance(response, list):
            return FakeStream(response)
        return response


class FakeChat:
    def __init__(self, responses) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class FakePortfolio:
    def __init__(self) -> None:
        self.queries = []

    async def search(self, query: str):
        self.queries.append(query)
        return [{"source": "projects.0", "text": '{"stack":["Rust"]}'}]


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


@pytest.mark.asyncio
async def test_general_route_has_no_tools() -> None:
    chat = FakeChat(
        [
            classifier_response(["general"]),
            [chunk('{"answer":"Hola."}'), chunk(finish_reason="stop")],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("Hola", [])]

    assert token_text(events) == "Hola."
    assert portfolio.queries == []
    assert chat.chat.completions.requests[0]["stream"] is False
    worker_request = chat.chat.completions.requests[1]
    assert worker_request["stream"] is True
    assert "tools" not in worker_request
    assert returned_context(events)[-1] == {"role": "assistant", "content": "Hola."}


@pytest.mark.asyncio
async def test_portfolio_route_exposes_only_portfolio_tool() -> None:
    chat = FakeChat(
        [
            classifier_response(["portfolio"]),
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-search",
                            name="search_portfolio",
                            arguments='{"query":"Rust"}',
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk('{"answer":"El portfolio confirma experiencia con Rust."}'),
                chunk(finish_reason="stop"),
            ],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [event async for event in agent.respond("¿Diego usa Rust?", [])]

    assert token_text(events) == "El portfolio confirma experiencia con Rust."
    assert portfolio.queries == ["Rust"]
    worker_request = chat.chat.completions.requests[1]
    assert worker_request["tools"] == [SEARCH_PORTFOLIO_SCHEMA]
    assert worker_request["parallel_tool_calls"] is False
    assert RESOLVE_DATETIME_SCHEMA not in worker_request["tools"]
    assert SET_REMINDER_MOCK_SCHEMA not in worker_request["tools"]


@pytest.mark.asyncio
async def test_temporal_route_exposes_only_temporal_tools() -> None:
    chat = FakeChat(
        [
            classifier_response(["temporal"]),
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-date",
                            name="resolve_datetime",
                            arguments=json.dumps(
                                {
                                    "reference": "now",
                                    "offset": 1,
                                    "unit": "days",
                                }
                            ),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk('{"answer":"Mañana será jueves."}'),
                chunk(finish_reason="stop"),
            ],
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("¿Qué fecha será mañana?", [])]

    assert token_text(events) == "Mañana será jueves."
    worker_request = chat.chat.completions.requests[1]
    assert worker_request["tools"] == [
        RESOLVE_DATETIME_SCHEMA,
        SET_REMINDER_MOCK_SCHEMA,
    ]
    assert SEARCH_PORTFOLIO_SCHEMA not in worker_request["tools"]


@pytest.mark.asyncio
async def test_mixed_routes_run_isolated_workers_and_compose_results() -> None:
    chat = FakeChat(
        [
            classifier_response(["portfolio", "temporal"]),
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-search",
                            name="search_portfolio",
                            arguments='{"query":"PocketTrace stack"}',
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                chunk('{"answer":"PocketTrace usa Rust."}'),
                chunk(finish_reason="stop"),
            ],
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
            ],
            [
                chunk('{"answer":"Hoy es miércoles."}'),
                chunk(finish_reason="stop"),
            ],
        ]
    )
    portfolio = FakePortfolio()
    agent = Agent("Diego", chat, portfolio, model="qwen")

    events = [
        event
        async for event in agent.respond(
            "¿Qué stack usa PocketTrace y qué fecha es hoy?",
            [],
            diagnostics=True,
        )
    ]

    assert token_text(events) == "PocketTrace usa Rust.\n\nHoy es miércoles."
    assert portfolio.queries == ["PocketTrace stack"]

    traces = [payload for event, payload in events if event == "trace"]
    assert len(traces) == 1
    assert traces[0]["dispatch"]["routes"] == ["portfolio", "temporal"]
    tool_names = [
        call["name"]
        for round_trace in traces[0]["rounds"]
        for call in round_trace.get("tool_calls", [])
    ]
    assert tool_names == ["search_portfolio", "resolve_datetime"]


@pytest.mark.asyncio
async def test_worker_json_is_not_exposed_to_the_visitor() -> None:
    chat = FakeChat(
        [
            classifier_response(["general"]),
            [chunk('{"answer":"Respuesta visible."}'), chunk(finish_reason="stop")],
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [event async for event in agent.respond("consulta", [])]

    assert token_text(events) == "Respuesta visible."
    assert '{"answer"' not in token_text(events)
