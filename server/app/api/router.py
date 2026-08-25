from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.scheduling.approval import BookingAlreadyConfirmed, BookingApproval, BookingExpired, BookingNotPending


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=96)
    message: str = Field(min_length=1, max_length=2000)


class BookingActionRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=96)


_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,96}$")


def encode_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class StreamingAgent(Protocol):
    def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]: ...


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=422, detail="Invalid session_id")


def create_router(agent: StreamingAgent, approvals: BookingApproval | None = None) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/stream")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        _validate_session_id(body.session_id)
        async def events() -> AsyncIterator[str]:
            yield encode_sse("ready", {"session_id": body.session_id})
            try:
                async for token in agent.respond(body.session_id, body.message.strip()):
                    if await request.is_disconnected():
                        return
                    yield encode_sse("token", {"text": token})
                if approvals is not None:
                    action = await approvals.pending_action(body.session_id)
                    if action is None:
                        yield encode_sse("action_cleared", {})
                    else:
                        yield encode_sse("action_required", {"type":"confirm_booking","booking_id":action.booking_id,"subject":action.subject,"visitor_name":action.visitor_name,"visitor_email":action.visitor_email,"start":action.start.isoformat(),"end":action.end.isoformat(),"expires_at":action.expires_at.isoformat() if action.expires_at is not None else None})
                yield encode_sse("done", {})
            except Exception:
                yield encode_sse("error", {"message":"The business representative is temporarily unavailable."})
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no"})

    if approvals is not None:
        @router.post("/v1/bookings/{booking_id}/confirm")
        async def confirm_booking(booking_id: str, body: BookingActionRequest) -> dict[str, object]:
            _validate_session_id(body.session_id)
            try:
                result = await approvals.confirm(body.session_id, booking_id)
            except BookingExpired as exc:
                raise HTTPException(status_code=410, detail=str(exc)) from exc
            except BookingNotPending as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if result is None:
                return {"status":"confirmed","booking_id":booking_id,"already_confirmed":True}
            return {"status":"confirmed","booking_id":result.booking_id,"event_id":result.event_id,"html_link":result.html_link,"start":result.start.isoformat(),"end":result.end.isoformat(),"already_confirmed":False}

        @router.post("/v1/bookings/{booking_id}/cancel")
        async def cancel_booking(booking_id: str, body: BookingActionRequest) -> dict[str, object]:
            _validate_session_id(body.session_id)
            try:
                await approvals.cancel(body.session_id, booking_id)
            except BookingAlreadyConfirmed as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except BookingNotPending as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return {"status":"cancelled","booking_id":booking_id}

    return router
