from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator

from .calendar_gateway import CalendarGateway
from .llama_client import LlamaClient, ToolCall
from .policies import SchedulingPolicy
from .profile import BusinessProfile
from .session import OfferedSlot, PendingBooking, SessionState, SessionStore
from .slot_service import SlotService

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class BusinessRepresentative:
    def __init__(
        self,
        profile: BusinessProfile,
        sessions: SessionStore,
        policy: SchedulingPolicy,
        slots: SlotService,
        calendar: CalendarGateway,
        llama: LlamaClient,
    ) -> None:
        self._profile = profile
        self._sessions = sessions
        self._policy = policy
        self._slots = slots
        self._calendar = calendar
        self._llama = llama
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return (
            "You are the digital business representative for the portfolio owner. "
            "Act like a concise, capable business concierge. Reply in the visitor's language. "
            "You are not the owner and must never claim to be human. "
            "Answer only from BUSINESS_CONTEXT for owner-specific facts; do not invent clients, rates, availability, results, or credentials. "
            "For scheduling, use tools instead of inventing free times. "
            "Never claim a meeting is booked until the server reports that the calendar write succeeded. "
            "If a tool says explicit confirmation is required, ask for that confirmation and stop. "
            "Keep normal answers under 120 words unless the visitor asks for detail.\n"
            f"BUSINESS_CONTEXT={self._profile.prompt_context()}"
        )

    def _messages(
        self,
        state: SessionState,
        extra: list[dict[str, Any]] | None = None,
        system_suffix: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build a Qwen-compatible conversation with exactly one leading system message."""
        local_now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        system_content = (
            f"{self._system_prompt}\n"
            f"CURRENT_TIME={local_now.isoformat()}\n"
            f"TIMEZONE={self._profile.scheduling.timezone}"
        )
        if system_suffix:
            system_content = f"{system_content}\n{system_suffix}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content}
        ]
        messages.extend({"role": turn.role, "content": turn.content} for turn in state.turns)
        if extra:
            messages.extend(extra)
        return messages

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_availability",
                    "description": "Get real free meeting slots from the owner's calendar for an inclusive date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "format": "date"},
                            "end_date": {"type": "string", "format": "date"},
                        },
                        "required": ["start_date", "end_date"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prepare_booking",
                    "description": (
                        "Prepare, but do not create, a meeting using a slot previously returned by get_availability. "
                        "Use only when visitor name, email, subject, and exact slot are known."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "slot_start": {"type": "string", "format": "date-time"},
                            "visitor_name": {"type": "string", "minLength": 2},
                            "visitor_email": {"type": "string"},
                            "subject": {"type": "string", "minLength": 3, "maxLength": 120},
                        },
                        "required": ["slot_start", "visitor_name", "visitor_email", "subject"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        state = await self._sessions.get(session_id)

        if state.pending_booking and self._policy.is_explicit_confirmation(user_message):
            await self._sessions.append_turn(state, "user", user_message)
            async for chunk in self._confirm_pending_booking(state):
                yield chunk
            return

        if state.pending_booking and self._policy.is_rejection(user_message):
            state.pending_booking = None

        if state.pending_booking is not None:
            await self._sessions.append_turn(state, "user", user_message)
            reminder = (
                "That meeting is still pending confirmation. Reply ‘confirm’ / ‘sí, confirmo’ "
                "to book it, or ‘cancel’ / ‘no’ to discard it and choose another time."
            )
            async for chunk in self._chunk(reminder):
                yield chunk
            await self._sessions.append_turn(state, "assistant", reminder)
            return

        await self._sessions.append_turn(state, "user", user_message)

        if not self._policy.maybe_scheduling_intent(user_message):
            content = ""
            async for chunk in self._llama.stream_chat(self._messages(state)):
                content += chunk
                yield chunk
            if content:
                await self._sessions.append_turn(state, "assistant", content)
            return

        first = await self._llama.chat(self._messages(state), tools=self._tool_definitions())
        if not first.tool_calls:
            content = first.content or "I need a little more detail before I can help with the schedule."
            async for chunk in self._chunk(content):
                yield chunk
            await self._sessions.append_turn(state, "assistant", content)
            return

        tool_call = first.tool_calls[0]
        tool_result = await self._execute_tool(state, tool_call)
        tool_context = [
            {
                "role": "assistant",
                "content": first.content or None,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.name,
                "content": json.dumps(tool_result, ensure_ascii=False),
            },
        ]

        content = ""
        async for chunk in self._llama.stream_chat(self._messages(state, extra=tool_context)):
            content += chunk
            yield chunk
        if content:
            await self._sessions.append_turn(state, "assistant", content)

    async def _execute_tool(self, state: SessionState, call: ToolCall) -> dict[str, Any]:
        if call.name == "get_availability":
            return await self._get_availability(state, call.arguments)
        if call.name == "prepare_booking":
            return self._prepare_booking(state, call.arguments)
        return {"ok": False, "error": "Unknown tool."}

    async def _get_availability(
        self,
        state: SessionState,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            start = date.fromisoformat(str(arguments["start_date"]))
            end = date.fromisoformat(str(arguments["end_date"]))
            slots = await self._slots.available_slots(start, end)
        except (KeyError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        state.offered_slots = slots
        state.pending_booking = None
        return {
            "ok": True,
            "timezone": self._profile.scheduling.timezone,
            "meeting_minutes": self._profile.scheduling.meeting_minutes,
            "slots": [
                {"start": slot.start.isoformat(), "end": slot.end.isoformat()} for slot in slots
            ],
        }

    def _prepare_booking(self, state: SessionState, arguments: dict[str, Any]) -> dict[str, Any]:
        email = str(arguments.get("visitor_email", "")).strip()
        if not _EMAIL_RE.match(email):
            return {"ok": False, "error": "A valid visitor email is required."}

        try:
            requested_start = datetime.fromisoformat(str(arguments["slot_start"]))
        except (KeyError, ValueError):
            return {"ok": False, "error": "slot_start must be a valid ISO date-time."}

        slot = self._find_offered_slot(state.offered_slots, requested_start)
        if slot is None:
            return {
                "ok": False,
                "error": "That slot was not offered or is stale. Check availability again before preparing the booking.",
            }

        pending = PendingBooking(
            booking_id=uuid.uuid4().hex,
            slot=slot,
            visitor_name=str(arguments.get("visitor_name", "")).strip(),
            visitor_email=email,
            subject=str(arguments.get("subject", "Meeting with Diego Cano")).strip(),
        )
        if len(pending.visitor_name) < 2 or len(pending.subject) < 3:
            return {"ok": False, "error": "Visitor name and meeting subject are required."}

        state.pending_booking = pending
        return {
            "ok": True,
            "status": "awaiting_explicit_confirmation",
            "booking_id": pending.booking_id,
            "slot": {"start": slot.start.isoformat(), "end": slot.end.isoformat()},
            "visitor_name": pending.visitor_name,
            "visitor_email": pending.visitor_email,
            "subject": pending.subject,
            "instruction": "Ask the visitor to explicitly confirm. Do not say the meeting is booked yet.",
        }

    async def _confirm_pending_booking(self, state: SessionState) -> AsyncIterator[str]:
        pending = state.pending_booking
        if pending is None:
            return

        try:
            result = await self._calendar.create_booking(
                pending,
                self._profile.scheduling.timezone,
            )
        except Exception:
            fallback = (
                "I couldn't write the meeting to the calendar, so nothing has been booked. "
                "Please try again in a moment."
            )
            state.pending_booking = None
            await self._sessions.append_turn(state, "assistant", fallback)
            async for chunk in self._chunk(fallback):
                yield chunk
            return

        state.last_booking_id = result.booking_id
        state.pending_booking = None
        confirmation_context = (
            "The calendar write succeeded. Confirm the booking briefly in the visitor's language. "
            f"BOOKING={{\"start\":\"{pending.slot.start.isoformat()}\","
            f"\"end\":\"{pending.slot.end.isoformat()}\","
            f"\"subject\":{json.dumps(pending.subject)},"
            f"\"email\":{json.dumps(pending.visitor_email)}}}"
        )
        content = ""
        try:
            async for chunk in self._llama.stream_chat(
                self._messages(state, system_suffix=confirmation_context)
            ):
                content += chunk
                yield chunk
        except Exception:
            content = (
                f"Booked: {pending.subject} on {pending.slot.start.strftime('%Y-%m-%d %H:%M %Z')}. "
                f"The invitation was sent to {pending.visitor_email}."
            )
            async for chunk in self._chunk(content):
                yield chunk
        if content:
            await self._sessions.append_turn(state, "assistant", content)

    @staticmethod
    def _find_offered_slot(
        slots: list[OfferedSlot],
        requested_start: datetime,
    ) -> OfferedSlot | None:
        for slot in slots:
            if slot.start == requested_start.astimezone(slot.start.tzinfo):
                return slot
        return None

    @staticmethod
    async def _chunk(text: str, size: int = 18) -> AsyncIterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]
