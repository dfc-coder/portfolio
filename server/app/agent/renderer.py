from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from app.domain.conversation import SessionState
from app.domain.planning import Observation, ObservationType
from app.ports.llm import GenerationConfig, LlmPort

from .context import ContextBuilder

_SPANISH_HINTS = {"que", "qué", "quiero", "puedo", "podemos", "reunion", "reunión", "horario", "mañana", "gracias", "hola", "el", "la", "me", "mi", "para", "con"}
_SPANISH_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class HybridRenderer:
    def __init__(self, llm: LlmPort, context: ContextBuilder, renderer_config: GenerationConfig, repair_config: GenerationConfig) -> None:
        self._llm = llm
        self._context = context
        self._renderer_config = renderer_config
        self._repair_config = repair_config

    async def stream_business_answer(self, state: SessionState) -> AsyncIterator[str]:
        async for chunk in self._llm.stream(self._context.business_messages(state), self._renderer_config):
            yield chunk

    async def business_answer(self, state: SessionState) -> str:
        return await self._llm.complete(self._context.business_messages(state), self._renderer_config)

    async def repair_business_answer(self, state: SessionState, candidate: str, issues: list[str]) -> str:
        return await self._llm.complete(self._context.business_repair_messages(state, candidate, issues), self._repair_config)

    def safety_fallback(self, state: SessionState) -> str:
        message = state.turns[-1].content if state.turns else ""
        return "No puedo afirmar eso sin información verificable en el contexto disponible." if self._is_spanish(message) else "I can't make that claim without verifiable information in the available context."

    def render_observation(self, observation: Observation, user_message: str, timezone_name: str) -> str:
        spanish = self._is_spanish(user_message)
        match observation.type:
            case ObservationType.AVAILABLE_SLOTS:
                return self._render_slots(observation, timezone_name, spanish)
            case ObservationType.MISSING_FIELDS:
                return self._render_missing(observation, spanish)
            case ObservationType.INVALID_SLOT:
                return "Ese horario no está entre los que ofrecí. Elegí uno de los horarios disponibles." if spanish else "That slot is not one I offered. Please choose one of the available slots."
            case ObservationType.AWAITING_CONFIRMATION:
                start = self._format_datetime(observation.data.get("start"), spanish)
                subject = str(observation.data.get("subject") or "reunión")
                return (f"Tengo preparada “{subject}” para {start}. Decime “sí, confirmo” para crearla en el calendario." if spanish else f"I have “{subject}” prepared for {start}. Reply “yes, confirm” to create it on the calendar.")
            case ObservationType.CANCELLED:
                return "Cancelado. No se creó ninguna reunión." if spanish else "Cancelled. No meeting was created."
            case ObservationType.BOOKED:
                start = self._format_datetime(observation.data.get("start"), spanish)
                subject = str(observation.data.get("subject") or "meeting")
                email = str(observation.data.get("visitor_email") or "")
                return f"Listo. “{subject}” quedó agendada para {start}. La invitación se envió a {email}." if spanish else f"Done. “{subject}” is booked for {start}. The invitation was sent to {email}."
            case ObservationType.TOOL_ERROR:
                return "No pude completar esa operación sin inventar información. Probemos otra vez." if spanish else "I couldn't complete that operation safely. Please try again."
            case _:
                return "Necesito un poco más de información para continuar." if spanish else "I need a little more information to continue."

    def confirmation_reminder(self, state: SessionState, user_message: str) -> str:
        spanish = self._is_spanish(user_message)
        pending = state.scheduling.pending_booking
        if pending is None:
            return ""
        start = self._format_datetime(pending.slot.start.isoformat(), spanish)
        return (f"La reunión para {start} sigue pendiente. Respondé “sí, confirmo” para agendarla o “cancelar” para descartarla." if spanish else f"The meeting for {start} is still pending. Reply “yes, confirm” to book it or “cancel” to discard it.")

    @classmethod
    def _render_slots(cls, observation: Observation, timezone_name: str, spanish: bool) -> str:
        slots = observation.data.get("slots") or []
        if not slots:
            return "No encontré horarios disponibles en ese rango. Decime otra fecha o rango." if spanish else "I couldn't find available slots in that range. Give me another date or range."
        lines = []
        for item in slots:
            if isinstance(item, dict):
                lines.append(f"- {item.get('id')}: {cls._format_datetime(item.get('start'), spanish)}")
        heading = f"Tengo estos horarios disponibles ({timezone_name}):" if spanish else f"I have these available times ({timezone_name}):"
        ending = "Decime cuál preferís; podés decir “el segundo” o “S2”." if spanish else "Tell me which you prefer; you can say “the second one” or “S2”."
        return "\n".join([heading, *lines, ending])

    @staticmethod
    def _render_missing(observation: Observation, spanish: bool) -> str:
        fields = list(observation.data.get("fields") or [])
        if fields == ["date_range"]:
            return "¿Qué día o rango de fechas te sirve para la reunión?" if spanish else "What day or date range works for the meeting?"
        labels_es = {"visitor_name": "tu nombre", "visitor_email": "tu email", "subject": "el tema de la reunión"}
        labels_en = {"visitor_name": "your name", "visitor_email": "your email", "subject": "the meeting topic"}
        labels = labels_es if spanish else labels_en
        needed = [labels.get(field, field) for field in fields]
        return f"Para preparar la reunión me falta: {', '.join(needed)}." if spanish else f"To prepare the meeting I still need: {', '.join(needed)}."

    @staticmethod
    def _format_datetime(value: Any, spanish: bool) -> str:
        if not value:
            return ""
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if spanish:
            return f"{_SPANISH_WEEKDAYS[parsed.weekday()]} {parsed.strftime('%d/%m')} a las {parsed.strftime('%H:%M')}"
        return parsed.strftime("%A %Y-%m-%d at %H:%M")

    @staticmethod
    def _is_spanish(text: str) -> bool:
        normalized = text.lower().replace("¿", "").replace("¡", "")
        words = {token.strip(".,;:!?()[]{}\"'") for token in normalized.split()}
        return bool(words & _SPANISH_HINTS) or any(char in normalized for char in "áéíóúñ")
