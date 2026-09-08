import copy
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.capabilities import CapabilityDecision


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


class ReminderSelector:
    async def select(self, message, context):
        return CapabilityDecision(
            names=("reminder",),
            route="reminder",
            requires_tool=True,
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
async def test_required_capability_exposes_only_one_tool_and_forces_first_call() -> None:
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
        capability_selector=ReminderSelector(),
    )

    events = [
        event
        async for event in agent.respond(
            "Recordame en 30 minutos revisar el portfolio.",
            [],
        )
    ]

    first = chat.chat.completions.requests[0]
    assert first["tool_choice"] == "required"
    assert first["parallel_tool_calls"] is False
    assert [tool["function"]["name"] for tool in first["tools"]] == [
        "set_reminder_mock"
    ]

    second = chat.chat.completions.requests[1]
    assert "tools" not in second
    assert "tool_choice" not in second

    running = [
        payload["name"]
        for event, payload in events
        if event == "tool" and payload["state"] == "running"
    ]
    assert running == ["set_reminder_mock"]
