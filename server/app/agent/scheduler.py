from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.ports.calendar import CalendarPort
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_SPANISH_HINTS = {"que", "qué", "quiero", "puedo", "podemos", "reunion", "reunión", "horario", "mañana", "gracias", "hola", "el", "la", "me", "mi", "para", "con", "si", "sí"}
_SPANISH_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class SchedulingIntent(StrEnum):
    REQUEST = "request"
    INFORM = "inform"
    SELECT = "select"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    OTHER = "other"


class SchedulingTurn(BaseModel):
    intent: SchedulingIntent
    start_date: date | None = None
    end_date: date | None = None
    slot_id: str | None = None
    visitor_name: str | None = None
    visitor_email: str | None = None
    subject: str | None = None


class SchedulerReply(BaseModel):
    text: str = ""
    not_applicable: bool = False


class Scheduler:
    """Small goal-oriented meeting workflow backed by structured memory, not a conversational FSM."""

    PUBLIC_CAPABILITIES = (
        "Check Diego's calendar availability for a date or date range.",
        "Prepare a meeting from one of the offered time slots.",
        "Create the meeting on the calendar after the visitor explicitly confirms it.",
    )

    def __init__(
        self,
        llm: LlmPort,
        slots: SlotService,
        calendar: CalendarPort,
        policy: SchedulingPolicy,
        config: GenerationConfig,
    ) -> None:
        self._llm = llm
        self._slots = slots
        self._calendar = calendar
        self._policy = policy
        self._config = config

    @property
    def public_capabilities(self) -> tuple[str, ...]:
        return self.PUBLIC_CAPABILITIES

    async def handle(self, state: SessionState, user_message: str, relation: RouteRelation) -> SchedulerReply:
        spanish = self._is_spanish(user_message)
        memory = state.scheduling

        # Write authorization is deterministic and does not depend on model interpretation.
        if memory.pending_booking is not None and self._policy.is_explicit_confirmation(user_message):
            return SchedulerReply(text=await self._create_booking(state, spanish))
        if state.active_workflow == ActiveWorkflow.SCHEDULING and self._policy.is_rejection(user_message):
            state.reset_scheduling()
            return SchedulerReply(text="Cancelado. No se creó ninguna reunión." if spanish else "Cancelled. No meeting was created.")

        turn = await self._interpret(state, user_message, relation)
        if turn.intent == SchedulingIntent.OTHER:
            return SchedulerReply(not_applicable=True)
        if turn.intent == SchedulingIntent.CANCEL:
            state.reset_scheduling()
            return SchedulerReply(text="Cancelado. No se creó ninguna reunión." if spanish else "Cancelled. No meeting was created.")

        state.active_workflow = ActiveWorkflow.SCHEDULING
        self._apply_turn(state, turn)

        if turn.intent == SchedulingIntent.CONFIRM and memory.pending_booking is not None:
            return SchedulerReply(text=self._confirmation_required(memory.pending_booking, spanish))

        if turn.slot_id:
            if turn.slot_id not in memory.offered_slots:
                return SchedulerReply(text="Ese horario no está entre los que ofrecí. Elegí uno de los horarios disponibles." if spanish else "That slot is not one I offered. Please choose one of the available slots.")
            memory.selected_slot_id = turn.slot_id
            memory.pending_booking = None

        if memory.requested_start_date is None or memory.requested_end_date is None:
            return SchedulerReply(text="¿Qué día o rango de fechas te sirve para la reunión?" if spanish else "What day or date range works for the meeting?")

        if not memory.offered_slots:
            try:
                slots = await self._slots.available_slots(memory.requested_start_date, memory.requested_end_date)
            except ValueError:
                return SchedulerReply(text="Ese rango no es válido para la agenda. Probemos con otra fecha." if spanish else "That range is not valid for the calendar. Try another date.")
            memory.offered_slots = {f"S{index}": slot for index, slot in enumerate(slots, start=1)}
            memory.selected_slot_id = None
            memory.pending_booking = None
            return SchedulerReply(text=self._render_slots(memory.offered_slots, spanish))

        if memory.selected_slot_id is None:
            return SchedulerReply(text=self._render_slots(memory.offered_slots, spanish))

        missing = memory.missing_details()
        if memory.visitor_email and not _EMAIL_RE.fullmatch(memory.visitor_email.strip()):
            missing = [field for field in missing if field != "visitor_email"]
            missing.append("visitor_email")
        if missing:
            return SchedulerReply(text=self._render_missing(missing, spanish))

        if memory.pending_booking is None:
            slot = memory.offered_slots.get(memory.selected_slot_id)
            if slot is None:
                memory.selected_slot_id = None
                return SchedulerReply(text=self._render_slots(memory.offered_slots, spanish))
            memory.pending_booking = PendingBooking(
                booking_id=uuid.uuid4().hex,
                slot=slot,
                visitor_name=memory.visitor_name or "",
                visitor_email=memory.visitor_email or "",
                subject=memory.subject or "",
            )

        return SchedulerReply(text=self._confirmation_required(memory.pending_booking, spanish))

    async def _interpret(self, state: SessionState, user_message: str, relation: RouteRelation) -> SchedulingTurn:
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)
        memory = state.scheduling
        payload = {
            "CURRENT_TIME": now.isoformat(),
            "TIMEZONE": self._policy.config.timezone,
            "RELATION": relation.value,
            "ACTIVE_SCHEDULING": state.active_workflow == ActiveWorkflow.SCHEDULING,
            "KNOWN": {
                "requested_start_date": memory.requested_start_date,
                "requested_end_date": memory.requested_end_date,
                "offered_slot_ids": list(memory.offered_slots),
                "selected_slot_id": memory.selected_slot_id,
                "has_name": bool(memory.visitor_name),
                "has_email": bool(memory.visitor_email),
                "has_subject": bool(memory.subject),
                "has_pending_booking": memory.pending_booking is not None,
            },
            "VISITOR_MESSAGE": user_message,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract meaning from the latest visitor turn only. Return SchedulingTurn JSON. "
                    "request=asks to arrange or check a meeting; inform=provides dates or meeting details; "
                    "select=chooses one offered slot; confirm=confirms a pending meeting; cancel=cancels meeting setup; "
                    "other=not scheduling. Questions about Diego's work, technologies, projects, rates, skills, "
                    "capabilities or tools are other even while meeting setup is active. Resolve relative dates using CURRENT_TIME. "
                    "Never invent fields that are absent from VISITOR_MESSAGE."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        try:
            raw = await self._llm.complete(messages, self._config, response_schema=SchedulingTurn)
            return SchedulingTurn.model_validate_json(raw)
        except Exception:
            return SchedulingTurn(intent=SchedulingIntent.OTHER)

    @staticmethod
    def _apply_turn(state: SessionState, turn: SchedulingTurn) -> None:
        memory = state.scheduling
        if turn.start_date is not None:
            changed = memory.requested_start_date != turn.start_date or memory.requested_end_date != (turn.end_date or turn.start_date)
            memory.requested_start_date = turn.start_date
            memory.requested_end_date = turn.end_date or turn.start_date
            if changed:
                memory.offered_slots.clear()
                memory.selected_slot_id = None
                memory.pending_booking = None
        if turn.visitor_name:
            memory.visitor_name = turn.visitor_name.strip()
        if turn.visitor_email:
            memory.visitor_email = turn.visitor_email.strip()
        if turn.subject:
            memory.subject = turn.subject.strip()

    async def _create_booking(self, state: SessionState, spanish: bool) -> str:
        memory = state.scheduling
        pending = memory.pending_booking
        if pending is None:
            return "No hay una reunión preparada para confirmar." if spanish else "There is no prepared meeting to confirm."
        if not _EMAIL_RE.fullmatch(pending.visitor_email.strip()):
            return "Necesito un email válido antes de crear la reunión." if spanish else "I need a valid email before creating the meeting."
        if memory.selected_slot_id is None or memory.selected_slot_id not in memory.offered_slots:
            return "El horario seleccionado ya no es válido. Elegí uno de los horarios disponibles." if spanish else "The selected slot is no longer valid. Choose one of the available slots."
        try:
            result = await self._calendar.create_booking(pending, self._policy.config.timezone)
        except Exception:
            return "No pude crear la reunión. La reserva sigue pendiente para que puedas reintentar." if spanish else "I couldn't create the meeting. The prepared booking is still pending so you can retry."

        state.last_booking_id = result.booking_id
        memory.pending_booking = None
        state.active_workflow = None
        start = self._format_datetime(pending.slot.start, spanish)
        if spanish:
            return f"Listo. “{pending.subject}” quedó agendada para {start}. La invitación se envió a {pending.visitor_email}."
        return f"Done. “{pending.subject}” is booked for {start}. The invitation was sent to {pending.visitor_email}."

    def _render_slots(self, slots: dict[str, OfferedSlot], spanish: bool) -> str:
        if not slots:
            return "No encontré horarios disponibles en ese rango. Decime otra fecha o rango." if spanish else "I couldn't find available slots in that range. Give me another date or range."
        heading = f"Tengo estos horarios disponibles ({self._policy.config.timezone}):" if spanish else f"I have these available times ({self._policy.config.timezone}):"
        lines = [f"- {slot_id}: {self._format_datetime(slot.start, spanish)}" for slot_id, slot in slots.items()]
        ending = "Decime cuál preferís; podés decir “el segundo” o “S2”." if spanish else "Tell me which you prefer; you can say “the second one” or “S2”."
        return "\n".join([heading, *lines, ending])

    @staticmethod
    def _render_missing(fields: list[str], spanish: bool) -> str:
        labels_es = {"visitor_name": "tu nombre", "visitor_email": "un email válido", "subject": "el tema de la reunión"}
        labels_en = {"visitor_name": "your name", "visitor_email": "a valid email", "subject": "the meeting topic"}
        labels = labels_es if spanish else labels_en
        needed = [labels.get(field, field) for field in dict.fromkeys(fields)]
        return f"Para preparar la reunión me falta: {', '.join(needed)}." if spanish else f"To prepare the meeting I still need: {', '.join(needed)}."

    @classmethod
    def _confirmation_required(cls, pending: PendingBooking, spanish: bool) -> str:
        start = cls._format_datetime(pending.slot.start, spanish)
        if spanish:
            return f"Tengo preparada “{pending.subject}” para {start}. Decime “sí, confirmo” para crearla en el calendario."
        return f"I have “{pending.subject}” prepared for {start}. Reply “yes, confirm” to create it on the calendar."

    @staticmethod
    def _format_datetime(value: datetime, spanish: bool) -> str:
        if spanish:
            return f"{_SPANISH_WEEKDAYS[value.weekday()]} {value.strftime('%d/%m')} a las {value.strftime('%H:%M')}"
        return value.strftime("%A %Y-%m-%d at %H:%M")

    @staticmethod
    def _is_spanish(text: str) -> bool:
        normalized = text.lower().replace("¿", "").replace("¡", "")
        words = {token.strip(".,;:!?()[]{}\"'") for token in normalized.split()}
        return bool(words & _SPANISH_HINTS) or any(char in normalized for char in "áéíóúñ")
