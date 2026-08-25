from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.ports.calendar import CalendarPort
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService
from app.scheduling.turn_parser import SchedulingIntent, SchedulingTurn, SchedulingTurnParser

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_APPROVAL_TTL = timedelta(minutes=15)
_SPANISH_HINTS = {
    "que",
    "qué",
    "quiero",
    "puedo",
    "podemos",
    "reunion",
    "reunión",
    "horario",
    "mañana",
    "gracias",
    "hola",
    "el",
    "la",
    "me",
    "mi",
    "para",
    "con",
    "si",
    "sí",
}
_SPANISH_WEEKDAYS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)


class SchedulerReply(BaseModel):
    text: str = ""
    not_applicable: bool = False


class Scheduler:
    """Meeting workflow. It may prepare bookings but never performs calendar writes."""

    PUBLIC_CAPABILITIES = (
        "Check Diego's calendar availability for a date or date range.",
        "Prepare a meeting from one of the offered time slots.",
        "Request explicit human approval before any meeting is created on the calendar.",
    )

    def __init__(
        self,
        llm: LlmPort,
        slots: SlotService,
        calendar: CalendarPort,
        policy: SchedulingPolicy,
        config: GenerationConfig,
    ) -> None:
        # Compatibility seam for existing diagnostics. The capability is deliberately
        # discarded, so Scheduler cannot perform calendar side effects.
        del calendar
        self._slots = slots
        self._policy = policy
        self._parser = SchedulingTurnParser(llm, policy, config)

    @property
    def public_capabilities(self) -> tuple[str, ...]:
        return self.PUBLIC_CAPABILITIES

    async def handle(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
    ) -> SchedulerReply:
        spanish = self._is_spanish(user_message)
        memory = state.scheduling

        if (
            state.active_workflow == ActiveWorkflow.SCHEDULING
            and self._policy.is_rejection(user_message)
        ):
            state.reset_scheduling()
            return SchedulerReply(
                text=(
                    "Cancelado. No se creó ninguna reunión."
                    if spanish
                    else "Cancelled. No meeting was created."
                )
            )

        turn = await self._interpret(state, user_message, relation)
        if turn.intent == SchedulingIntent.OTHER:
            return SchedulerReply(not_applicable=True)
        if turn.intent == SchedulingIntent.CANCEL:
            state.reset_scheduling()
            return SchedulerReply(
                text=(
                    "Cancelado. No se creó ninguna reunión."
                    if spanish
                    else "Cancelled. No meeting was created."
                )
            )

        state.active_workflow = ActiveWorkflow.SCHEDULING
        self._apply_turn(state, turn)

        if turn.intent == SchedulingIntent.CONFIRM and memory.pending_booking is not None:
            return SchedulerReply(
                text=self._approval_required(memory.pending_booking, spanish)
            )

        if turn.slot_id:
            if turn.slot_id not in memory.offered_slots:
                return SchedulerReply(
                    text=(
                        "Ese horario no está entre los que ofrecí. Elegí uno de los horarios disponibles."
                        if spanish
                        else "That slot is not one I offered. Please choose one of the available slots."
                    )
                )
            memory.selected_slot_id = turn.slot_id
            memory.pending_booking = None

        if memory.requested_start_date is None or memory.requested_end_date is None:
            return SchedulerReply(
                text=(
                    "¿Qué día o rango de fechas te sirve para la reunión?"
                    if spanish
                    else "What day or date range works for the meeting?"
                )
            )

        if not memory.offered_slots:
            try:
                slots = await self._slots.available_slots(
                    memory.requested_start_date,
                    memory.requested_end_date,
                )
            except ValueError:
                return SchedulerReply(
                    text=(
                        "Ese rango no es válido para la agenda. Probemos con otra fecha."
                        if spanish
                        else "That range is not valid for the calendar. Try another date."
                    )
                )
            memory.offered_slots = {
                f"S{index}": slot for index, slot in enumerate(slots, start=1)
            }
            memory.selected_slot_id = None
            memory.pending_booking = None
            return SchedulerReply(
                text=self._render_slots(memory.offered_slots, spanish)
            )

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
                return SchedulerReply(
                    text=self._render_slots(memory.offered_slots, spanish)
                )
            memory.pending_booking = PendingBooking(
                booking_id=uuid.uuid4().hex,
                slot=slot,
                visitor_name=memory.visitor_name or "",
                visitor_email=memory.visitor_email or "",
                subject=memory.subject or "",
                expires_at=datetime.now(timezone.utc) + _APPROVAL_TTL,
            )

        return SchedulerReply(
            text=self._approval_required(memory.pending_booking, spanish)
        )

    async def _interpret(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
    ) -> SchedulingTurn:
        return await self._parser.parse(state, user_message, relation)

    @staticmethod
    def _apply_turn(state: SessionState, turn: SchedulingTurn) -> None:
        memory = state.scheduling
        if turn.start_date is not None:
            changed = (
                memory.requested_start_date != turn.start_date
                or memory.requested_end_date != (turn.end_date or turn.start_date)
            )
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

    def _render_slots(self, slots: dict[str, OfferedSlot], spanish: bool) -> str:
        if not slots:
            return (
                "No encontré horarios disponibles en ese rango. Decime otra fecha o rango."
                if spanish
                else "I couldn't find available slots in that range. Give me another date or range."
            )
        heading = (
            f"Tengo estos horarios disponibles ({self._policy.config.timezone}):"
            if spanish
            else f"I have these available times ({self._policy.config.timezone}):"
        )
        lines = [
            f"- {slot_id}: {self._format_datetime(slot.start, spanish)}"
            for slot_id, slot in slots.items()
        ]
        ending = (
            "Decime cuál preferís; podés decir “el segundo” o “S2”."
            if spanish
            else "Tell me which you prefer; you can say “the second one” or “S2”."
        )
        return "\n".join([heading, *lines, ending])

    @staticmethod
    def _render_missing(fields: list[str], spanish: bool) -> str:
        labels_es = {
            "visitor_name": "tu nombre",
            "visitor_email": "un email válido",
            "subject": "el tema de la reunión",
        }
        labels_en = {
            "visitor_name": "your name",
            "visitor_email": "a valid email",
            "subject": "the meeting topic",
        }
        labels = labels_es if spanish else labels_en
        needed = [labels.get(field, field) for field in dict.fromkeys(fields)]
        return (
            f"Para preparar la reunión me falta: {', '.join(needed)}."
            if spanish
            else f"To prepare the meeting I still need: {', '.join(needed)}."
        )

    @classmethod
    def _approval_required(cls, pending: PendingBooking, spanish: bool) -> str:
        start = cls._format_datetime(pending.slot.start, spanish)
        if spanish:
            return (
                f"Tengo preparada “{pending.subject}” para {start}. "
                "Revisá los datos y usá el botón “Confirmar reunión” para autorizar "
                "su creación en el calendario."
            )
        return (
            f'I have “{pending.subject}” prepared for {start}. '
            'Review the details and use “Confirm meeting” to authorize creating it '
            "on the calendar."
        )

    @staticmethod
    def _format_datetime(value: datetime, spanish: bool) -> str:
        if spanish:
            return (
                f"{_SPANISH_WEEKDAYS[value.weekday()]} {value.strftime('%d/%m')} "
                f"a las {value.strftime('%H:%M')}"
            )
        return value.strftime("%A %Y-%m-%d at %H:%M")

    @staticmethod
    def _is_spanish(text: str) -> bool:
        normalized = text.lower().replace("¿", "").replace("¡", "")
        words = {
            token.strip(".,;:!?()[]{}\"'") for token in normalized.split()
        }
        return bool(words & _SPANISH_HINTS) or any(
            char in normalized for char in "áéíóúñ"
        )


__all__ = ["Scheduler", "SchedulerReply", "SchedulingIntent", "SchedulingTurn"]
