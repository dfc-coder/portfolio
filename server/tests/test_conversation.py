import pytest

from app.conversation import ConversationStore


@pytest.mark.asyncio
async def test_conversation_store_persists_context_between_turns() -> None:
    store = ConversationStore()

    async with store.turn(
        None,
        seed_context=[{"role": "assistant", "content": "inicio"}],
    ) as first:
        conversation_id = first.conversation_id
        assert first.context == [{"role": "assistant", "content": "inicio"}]
        first.commit(
            [
                {"role": "assistant", "content": "inicio"},
                {"role": "user", "content": "¿Diego usa Rust?"},
                {"role": "assistant", "content": "Sí."},
            ]
        )

    async with store.turn(conversation_id) as second:
        assert second.context == [
            {"role": "assistant", "content": "inicio"},
            {"role": "user", "content": "¿Diego usa Rust?"},
            {"role": "assistant", "content": "Sí."},
        ]


@pytest.mark.asyncio
async def test_conversation_store_keeps_complete_tool_context() -> None:
    store = ConversationStore()
    tool_context = [
        {"role": "user", "content": "¿Qué fecha será mañana?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-date",
                    "type": "function",
                    "function": {
                        "name": "resolve_datetime",
                        "arguments": '{"reference":"now","offset":1,"unit":"days"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-date",
            "content": '{"ok":true,"result":{"date":"2026-09-08"}}',
        },
        {"role": "assistant", "content": "Mañana es 2026-09-08."},
    ]

    async with store.turn(None) as first:
        conversation_id = first.conversation_id
        first.commit(tool_context)

    async with store.turn(conversation_id) as second:
        assert second.context == tool_context


@pytest.mark.asyncio
async def test_conversation_store_bounds_message_history() -> None:
    store = ConversationStore(max_messages=3)
    messages = [
        {"role": "user", "content": str(index)}
        for index in range(5)
    ]

    async with store.turn(None) as turn:
        conversation_id = turn.conversation_id
        turn.commit(messages)

    async with store.turn(conversation_id) as turn:
        assert [item["content"] for item in turn.context] == ["2", "3", "4"]
