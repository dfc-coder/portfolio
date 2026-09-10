import copy
import json
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.temporal import DATETIME_REQUEST_SCHEMA, REMINDER_REQUEST_SCHEMA
from app.tools import RESOLVE_DATETIME_SCHEMA, SEARCH_PORTFOLIO_SCHEMA, SET_REMINDER_MOCK_SCHEMA


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


def response(content: str, *, finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
    )


def classifier_response(routes: list[str]) -> SimpleNamespace:
    return response(json.dumps({"routes": routes}))


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
        item = next(self._responses)
        if isinstance(item, list):
            return FakeStream(item)
        return item


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
async def test_datetime_route_uses_constrained_output_without_native_tools() -> None:
    chat = FakeChat(
        [
            classifier_response(["datetime"]),
            response(
                json.dumps(
                    {
                        "kind": "weekday",
                        "reference": "2026-12-25",
                        "offset": 0,
                        "unit": "days",
                        "language": "es",
                    }
                )
            ),
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [
        event
        async for event in agent.respond(
            "¿Qué día de la semana cae el 25 de diciembre de 2026?",
            [],
            diagnostics=True,
        )
    ]

    assert token_text(events) == "El 25 de diciembre de 2026 es viernes."
    assert len(chat.chat.completions.requests) == 2
    structured_request = chat.chat.completions.requests[1]
    assert structured_request["stream"] is False
    assert "tools" not in structured_request
    assert structured_request["extra_body"]["json_schema"] == DATETIME_REQUEST_SCHEMA
    assert "JSON Schema" not in structured_request["messages"][0]["content"]

    traces = [payload for event, payload in events if event == "trace"]
    calls = traces[0]["rounds"][0]["tool_calls"]
    assert calls[0]["name"] == "resolve_datetime"
    assert calls[0]["arguments"] == {
        "reference": "2026-12-25",
        "offset": 0,
        "unit": "days",
    }
    assert calls[0]["direct"] is True


@pytest.mark.asyncio
async def test_reminder_route_uses_constrained_output_without_native_tools() -> None:
    chat = FakeChat(
        [
            classifier_response(["reminder"]),
            response(
                json.dumps(
                    {
                        "reference": "2026-12-01T10:30:00-03:00",
                        "offset": 0,
                        "unit": "days",
                        "message": "Enviar la propuesta",
                        "language": "es",
                    }
                )
            ),
        ]
    )
    agent = Agent("Diego", chat, FakePortfolio(), model="qwen")

    events = [
        event
        async for event in agent.respond(
            "Recordame el 2026-12-01T10:30:00-03:00 enviar la propuesta.",
            [],
            diagnostics=True,
        )
    ]

    answer = token_text(events)
    assert "Recordatorio simulado creado" in answer
    assert "No es persistente" in answer
    assert len(chat.chat.completions.requests) == 2
    structured_request = chat.chat.completions.requests[1]
    assert "tools" not in structured_request
    assert structured_request["extra_body"]["json_schema"] == REMINDER_REQUEST_SCHEMA

    traces = [payload for event, payload in events if event == "trace"]
    calls = traces[0]["rounds"][0]["tool_calls"]
    assert calls[0]["name"] == "set_reminder_mock"
    assert calls[0]["direct"] is True


@pytest.mark.asyncio
async def test_mixed_routes_run_isolated_workers_and_compose_results() -> None:
    chat = FakeChat(
        [
            classifier_response(["portfolio", "datetime"]),
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
            response(
                json.dumps(
                    {
                        "kind": "date",
                        "reference": "2026-09-09",
                        "offset": 0,
                        "unit": "days",
                        "language": "es",
                    }
                )
            ),
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

    assert token_text(events) == "PocketTrace usa Rust.\n\nFecha: miércoles, 9 de septiembre de 2026."
    assert portfolio.queries == ["PocketTrace stack"]

    traces = [payload for event, payload in events if event == "trace"]
    assert len(traces) == 1
    assert traces[0]["dispatch"]["routes"] == ["portfolio", "datetime"]
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
