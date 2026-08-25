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


def is_new_scheduling_request(message: str) -> bool:
    """Admit only explicit meeting requests into a new operational workflow."""
    text = message.strip()
    return bool(_MEETING_OBJECT.search(text) and _MEETING_ACTION.search(text))
