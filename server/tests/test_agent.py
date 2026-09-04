import copy
import json
from types import SimpleNamespace

import pytest

from app.agent import Agent


def tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def message(content=None, tool_calls=None) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


class FakeCompletions:
    def __init__(self, responses) -> None:
        self._responses = iter(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return SimpleNamespace(
            choices=[SimpleNamespace(message=next(self._responses), finish_reason="stop")]
        )


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
async def test_agent_answers_without_tool_when_none_is_needed() -> None:
    chat = FakeChat([message("Hola.")])
    portfolio = FakePortfolio()
    agent = Agent(
        "Diego",
        chat,
        portfolio,
        model="qwen",
        timezone="America/Argentina/Buenos_Aires",
    )

    response = "".join([part async for part in agent.respond("hola", [])])

    assert response == "Hola."
    assert portfolio.queries == []
    assert len(chat.chat.completions.requests) == 1


@pytest.mark.asyncio
async def test_agent_preserves_tool_call_and_result_messages() -> None:
    chat = FakeChat(
        [
            message(
                tool_calls=[
                    tool_call("call-search", "search_portfolio", {"query": "Rust experience"})
                ]
            ),
            message("El perfil incluye experiencia con Rust."),
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

    response = "".join(
        [part async for part in agent.respond("¿Trabajó con Rust?", [])]
    )

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
            message(tool_calls=[tool_call("call-now", "get_current_datetime", {})]),
            message(
                tool_calls=[
                    tool_call(
                        "call-add",
                        "add_duration_to_datetime",
                        {
                            "datetime": "2030-01-01T10:00:00-03:00",
                            "days": 30,
                        },
                    )
                ]
            ),
            message(
                tool_calls=[
                    tool_call(
                        "call-reminder",
                        "set_reminder_mock",
                        {
                            "datetime": "2030-01-31T10:00:00-03:00",
                            "message": "Revisar el CV",
                        },
                    )
                ]
            ),
            message("Recordatorio simulado para el 31 de enero."),
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

    assert response == "Recordatorio simulado para el 31 de enero."
    assert len(chat.chat.completions.requests) == 4

    final_messages = chat.chat.completions.requests[-1]["messages"]
    tool_ids = [
        item["tool_call_id"]
        for item in final_messages
        if item["role"] == "tool"
    ]
    assert tool_ids == ["call-now", "call-add", "call-reminder"]


@pytest.mark.asyncio
async def test_agent_returns_multiple_tool_results_in_one_round() -> None:
    chat = FakeChat(
        [
            message(
                tool_calls=[
                    tool_call("call-search", "search_portfolio", {"query": "Rust"}),
                    tool_call(
                        "call-date",
                        "add_duration_to_datetime",
                        {
                            "datetime": "2030-01-01T10:00:00-03:00",
                            "days": 1,
                        },
                    ),
                ]
            ),
            message("Listo."),
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
