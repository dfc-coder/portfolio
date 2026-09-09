import copy
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.tool_search import ToolSelection
from app.tools import SET_REMINDER_MOCK_SCHEMA


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
    async def search(self, query: str):
        raise AssertionError(f"portfolio search must not run: {query}")


class ReminderToolSearch:
    async def select(self, message, context):
        return ToolSelection(
            tools=[SET_REMINDER_MOCK_SCHEMA],
            scores={"set_reminder_mock": 1.0},
            latency_ms=0.0,
        )


def chunk(content=None, *, tool_calls=None, finish_reason=None):
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


def tool_delta(index, *, call_id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.mark.asyncio
async def test_selected_tool_is_optional_and_remains_available_after_call() -> None:
    chat = FakeChat(
        [
            [
                chunk(
                    tool_calls=[
                        tool_delta(
                            0,
                            call_id="call-reminder",
                            name="set_reminder_mock",
                            arguments=(
                                '{"reference":"now","offset":30,"unit":"minutes",'
                                '"message":"revisar el portfolio"}'
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
        tool_search=ReminderToolSearch(),
    )

    events = [
        event
        async for event in agent.respond(
            "Recordame en 30 minutos revisar el portfolio.",
            [],
        )
    ]

    first = chat.chat.completions.requests[0]
    assert "tool_choice" not in first
    assert first["parallel_tool_calls"] is False
    assert [tool["function"]["name"] for tool in first["tools"]] == [
        "set_reminder_mock"
    ]

    second = chat.chat.completions.requests[1]
    assert "tool_choice" not in second
    assert [tool["function"]["name"] for tool in second["tools"]] == [
        "set_reminder_mock"
    ]

    running = [
        payload["name"]
        for event, payload in events
        if event == "tool" and payload["state"] == "running"
    ]
    assert running == ["set_reminder_mock"]
