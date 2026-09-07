import json
from types import SimpleNamespace

import pytest

from app.capabilities import ModelCapabilitySelector


class FakeUsage:
    def model_dump(self, *, exclude_none=True):
        return {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class FakeCompletions:
    def __init__(self, arguments: dict[str, bool]) -> None:
        self.arguments = arguments
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        call = SimpleNamespace(
            function=SimpleNamespace(
                name="select_capabilities",
                arguments=json.dumps(self.arguments),
            )
        )
        message = SimpleNamespace(tool_calls=[call])
        choice = SimpleNamespace(message=message, finish_reason="tool_calls")
        return SimpleNamespace(choices=[choice], usage=FakeUsage())


class FakeChat:
    def __init__(self, arguments: dict[str, bool]) -> None:
        self.completions = FakeCompletions(arguments)
        self.chat = SimpleNamespace(completions=self.completions)


@pytest.mark.asyncio
async def test_capability_selector_can_return_no_tools() -> None:
    chat = FakeChat(
        {"portfolio": False, "datetime": False, "reminder": False}
    )
    selector = ModelCapabilitySelector(chat, model="qwen")

    decision = await selector.select("Hola", [])

    assert decision.names == ()
    request = chat.completions.requests[0]
    assert request["temperature"] == 0
    assert request["parallel_tool_calls"] is False
    assert request["tool_choice"] == "required"
    assert [tool["function"]["name"] for tool in request["tools"]] == [
        "select_capabilities"
    ]


@pytest.mark.asyncio
async def test_capability_selector_supports_mixed_turns() -> None:
    chat = FakeChat(
        {"portfolio": True, "datetime": True, "reminder": False}
    )
    selector = ModelCapabilitySelector(chat, model="qwen")

    decision = await selector.select(
        "¿Qué stack usa PocketTrace y qué fecha es hoy?",
        [],
    )

    assert decision.names == ("portfolio", "datetime")
    assert decision.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


@pytest.mark.asyncio
async def test_capability_selector_receives_recent_context_for_followups() -> None:
    chat = FakeChat(
        {"portfolio": True, "datetime": False, "reminder": False}
    )
    selector = ModelCapabilitySelector(chat, model="qwen")

    await selector.select(
        "¿Y Go?",
        [
            {"role": "user", "content": "¿Diego usa Rust?"},
            {"role": "assistant", "content": "Sí."},
        ],
    )

    gate_message = chat.completions.requests[0]["messages"][1]["content"]
    assert "¿Diego usa Rust?" in gate_message
    assert "¿Y Go?" in gate_message
