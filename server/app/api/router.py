from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import PortfolioAgent


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=8)


def encode_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_router(agent: PortfolioAgent) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        history = [item.model_dump() for item in body.history]

        async def events() -> AsyncIterator[str]:
            try:
                async for token in agent.respond(body.message.strip(), history):
                    if await request.is_disconnected():
                        return
                    yield encode_sse("token", {"text": token})
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
