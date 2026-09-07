from __future__ import annotations

import asyncio
import copy
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

MAX_CONVERSATIONS = 512
MAX_MESSAGES = 32


@dataclass
class ConversationTurn:
    conversation_id: str
    context: list[dict[str, Any]]
    _store: "ConversationStore"

    def commit(self, messages: list[dict[str, Any]]) -> None:
        self._store._replace(self.conversation_id, messages)
        self.context = copy.deepcopy(self._store._messages[self.conversation_id])


class ConversationStore:
    def __init__(
        self,
        *,
        max_conversations: int = MAX_CONVERSATIONS,
        max_messages: int = MAX_MESSAGES,
    ) -> None:
        self._max_conversations = max_conversations
        self._max_messages = max_messages
        self._messages: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def turn(
        self,
        conversation_id: str | None,
        *,
        seed_context: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ConversationTurn]:
        resolved = _conversation_id(conversation_id)
        lock = self._locks.setdefault(resolved, asyncio.Lock())

        async with lock:
            if resolved not in self._messages:
                self._replace(resolved, seed_context or [])
            else:
                self._messages.move_to_end(resolved)

            yield ConversationTurn(
                conversation_id=resolved,
                context=copy.deepcopy(self._messages[resolved]),
                _store=self,
            )

    def _replace(self, conversation_id: str, messages: list[dict[str, Any]]) -> None:
        self._messages[conversation_id] = copy.deepcopy(
            _trim_messages(messages, self._max_messages)
        )
        self._messages.move_to_end(conversation_id)
        self._prune()

    def _prune(self) -> None:
        while len(self._messages) > self._max_conversations:
            conversation_id, _ = self._messages.popitem(last=False)
            self._locks.pop(conversation_id, None)


def _trim_messages(
    messages: list[dict[str, Any]],
    max_messages: int,
) -> list[dict[str, Any]]:
    if len(messages) <= max_messages:
        return messages

    start = len(messages) - max_messages
    while start < len(messages) and messages[start].get("role") != "user":
        start += 1
    return messages[start:]


def _conversation_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("conversation_id must be a valid UUID") from exc
