from __future__ import annotations

import json
import secrets
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


def create_router(agent: Agent, *, diagnostics_token: str | None = None) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        diagnostics = _diagnostics_allowed(
            request.headers.get("x-agent-diagnostics-token"),
            diagnostics_token,
        )

        async def events() -> AsyncIterator[str]:
            try:
                stream = (
                    agent.respond(body.message.strip(), body.context, diagnostics=True)
                    if diagnostics
                    else agent.respond(body.message.strip(), body.context)
                )
                async for event, payload in stream:
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
