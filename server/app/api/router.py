from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import Agent
from app.conversation import ConversationStore


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    context: list[dict[str, Any]] = Field(default_factory=list, max_length=32)


def encode_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_router(
    agent: Agent,
    *,
    diagnostics_token: str | None = None,
    conversations: ConversationStore | None = None,
) -> APIRouter:
    router = APIRouter()
    conversations = conversations or ConversationStore()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        diagnostics = _diagnostics_allowed(
            request.headers.get("x-agent-diagnostics-token"),
            diagnostics_token,
        )

        async def events() -> AsyncIterator[str]:
            try:
                conversation_id = str(body.conversation_id) if body.conversation_id else None
                async with conversations.turn(
                    conversation_id,
                    seed_context=body.context,
                ) as turn:
                    yield encode_sse(
                        "conversation",
                        {"conversation_id": turn.conversation_id},
                    )

                    stream = (
                        agent.respond(body.message.strip(), turn.context, diagnostics=True)
                        if diagnostics
                        else agent.respond(body.message.strip(), turn.context)
                    )
                    async for event, payload in stream:
                        if event == "context":
                            messages = payload.get("messages")
                            if isinstance(messages, list):
                                turn.commit(messages)

                        if await request.is_disconnected():
                            return
                        yield encode_sse(event, payload)
            except Exception:
                yield encode_sse(
                    "error",
                    {"message": "The portfolio assistant is temporarily unavailable."},
                )

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    return router


def _diagnostics_allowed(provided: str | None, expected: str | None) -> bool:
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)
