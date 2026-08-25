from __future__ import annotations

import re

_MEETING_OBJECT = re.compile(
    r"\b(?:reuni[oó]n|reuniones|meeting|meetings|call|llamada)\b",
    re.IGNORECASE,
)
_MEETING_ACTION = re.compile(
    r"\b(?:quiero|quisiera|querr[ií]a|podemos|coordinar|agendar|agendemos|reservar|"
    r"i(?:'|’)d\s+like|i\s+would\s+like|can\s+we|could\s+we|arrange|schedule|book|set\s+up)\b",
    re.IGNORECASE,
)
_AVAILABILITY_ES = re.compile(
    r"\b(?:disponibilidad|disponible|disponibles|horario|horarios)\b",
    re.IGNORECASE,
)
_AVAILABILITY_EN = re.compile(
    r"\b(?:availability|available|free\s+time|time\s+slots?|slots?)\b",
    re.IGNORECASE,
)


def is_availability_request(message: str) -> bool:
    """True for an explicit request to inspect calendar availability."""
    text = message.strip()
    return bool(_AVAILABILITY_ES.search(text) or _AVAILABILITY_EN.search(text))


def availability_clarification(message: str) -> str:
    """Ask for the minimum missing input needed to query availability."""
    if _AVAILABILITY_ES.search(message):
        return "¿Qué día o rango de fechas querés que consulte en la agenda de Diego?"
    return "What day or date range would you like me to check on Diego's calendar?"


def is_new_scheduling_request(message: str) -> bool:
    """Admit explicit meeting or availability requests into the operational workflow."""
    text = message.strip()
    explicit_meeting = bool(_MEETING_OBJECT.search(text) and _MEETING_ACTION.search(text))
    return explicit_meeting or is_availability_request(text)
