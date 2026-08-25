from __future__ import annotations

from datetime import datetime

from app.scheduling.result import SchedulerReply, SchedulerReplyKind, SlotOption

_SPANISH_WEEKDAYS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)


class SchedulingPresenter:
    """Render deterministic scheduling results using the browser locale."""

    def __init__(self, timezone: str) -> None:
        self._timezone = timezone

    def render(self, reply: SchedulerReply, locale: str) -> str:
        spanish = locale.lower().startswith("es")

        if reply.kind == SchedulerReplyKind.CANCELLED:
            return (
                "Cancelado. No se creó ninguna reunión."
                if spanish
                else "Cancelled. No meeting was created."
            )
        if reply.kind == SchedulerReplyKind.NEED_DATE:
            return (
                "¿Qué día o rango de fechas te sirve para la reunión?"
                if spanish
                else "What day or date range works for the meeting?"
            )
        if reply.kind == SchedulerReplyKind.INVALID_RANGE:
            return (
                "Ese rango no es válido para la agenda. Probemos con otra fecha."
                if spanish
                else "That range is not valid for the calendar. Try another date."
            )
        if reply.kind == SchedulerReplyKind.INVALID_SLOT:
            prefix = (
                "Ese horario no está entre los disponibles."
                if spanish
                else "That time is not among the available slots."
            )
            slots = self._render_slots(reply.slots, spanish)
            return f"{prefix}\n{slots}" if slots else prefix
        if reply.kind in {SchedulerReplyKind.SLOTS, SchedulerReplyKind.NO_SLOTS}:
            return self._render_slots(reply.slots, spanish)
        if reply.kind == SchedulerReplyKind.MISSING_DETAILS:
            return self._render_missing(reply.missing_fields, spanish)
        if reply.kind == SchedulerReplyKind.APPROVAL_REQUIRED:
            return self._render_approval(reply, spanish)
        return ""

    def _render_slots(self, slots: list[SlotOption], spanish: bool) -> str:
        if not slots:
            return (
                "No encontré horarios disponibles en los próximos días."
                if spanish
                else "I couldn't find available slots in the upcoming days."
            )

        heading = (
            f"Estos son los próximos horarios disponibles ({self._timezone}):"
            if spanish
            else f"These are the next available times ({self._timezone}):"
        )
        lines = [
            f"- {slot.slot_id}: {self._format_datetime(slot.start, spanish)}"
            for slot in slots
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

    def _render_approval(self, reply: SchedulerReply, spanish: bool) -> str:
        if reply.start is None:
            return ""
        start = self._format_datetime(reply.start, spanish)
        subject = reply.subject or "reunión"
        if spanish:
            return (
                f"Tengo preparada “{subject}” para {start}. "
                "Revisá los datos y usá el botón “Confirmar reunión” para autorizar "
                "su creación en el calendario."
            )
        return (
            f'I have “{subject}” prepared for {start}. '
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
