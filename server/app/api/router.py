from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import Agent


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: list[dict[str, Any]] = Field(default_factory=list, max_length=32)


def encode_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_router(agent: Agent) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            try:
                async for event, payload in agent.respond(body.message.strip(), body.context):
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
