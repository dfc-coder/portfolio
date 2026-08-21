from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .schemas import ChatRequest
from .sse import encode_sse

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,96}$")


class StreamingAgent(Protocol):
    def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]: ...


def create_router(agent: StreamingAgent) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        if not _SESSION_RE.fullmatch(body.session_id):
            raise HTTPException(status_code=422, detail="Invalid session_id")

        async def events() -> AsyncIterator[str]:
            yield encode_sse("ready", {"session_id": body.session_id})
            try:
                async for token in agent.respond(body.session_id, body.message.strip()):
                    if await request.is_disconnected():
                        return
                    yield encode_sse("token", {"text": token})
                yield encode_sse("done", {})
            except Exception:
                yield encode_sse(
                    "error",
                    {"message": "The business representative is temporarily unavailable."},
                )

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return router
