from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Final

from pydantic import BaseModel

from app.domain.conversation import SessionState
from app.domain.routing import RouteRelation
from app.ports.llm import GenerationConfig, LlmPort
from app.scheduling.policy import SchedulingPolicy

_EMAIL_RE: Final = re.compile(r"(?<![\w.+-])([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})(?![\w.-])")
_DIRECT_SLOT_RE: Final = re.compile(r"\bS\s*(\d{1,2})\b", re.IGNORECASE)
_NUMBERED_SLOT_RE: Final = re.compile(r"\b(?:slot|opci[oó]n|option|horario)\s*(?:n(?:ro)?\.?\s*)?(\d{1,2})\b", re.IGNORECASE)

_ORDINALS: Final[dict[str, int]] = {
    "first": 1,
    "primero": 1,
    "primera": 1,
    "primer": 1,
    "second": 2,
    "segundo": 2,
    "segunda": 2,
    "third": 3,
    "tercero": 3,
    "tercera": 3,
    "fourth": 4,
    "cuarto": 4,
    "cuarta": 4,
    "fifth": 5,
    "quinto": 5,
    "quinta": 5,
    "sixth": 6,
    "sexto": 6,
    "sexta": 6,
    "seventh": 7,
    "septimo": 7,
    "séptimo": 7,
    "septima": 7,
    "séptima": 7,
    "eighth": 8,
    "octavo": 8,
    "octava": 8,
    "ninth": 9,
    "noveno": 9,
    "novena": 9,
    "tenth": 10,
    "decimo": 10,
    "décimo": 10,
    "decima": 10,
    "décima": 10,
}

_MONTHS: Final[dict[str, int]] = {
    "january": 1,
    "enero": 1,
    "february": 2,
    "febrero": 2,
    "march": 3,
    "marzo": 3,
    "april": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "june": 6,
    "junio": 6,
    "july": 7,
    "julio": 7,
    "august": 8,
    "agosto": 8,
    "september": 9,
    "septiembre": 9,
    "setiembre": 9,
    "october": 10,
    "octubre": 10,
    "november": 11,
    "noviembre": 11,
    "december": 12,
    "diciembre": 12,
}
_MONTH_PATTERN: Final = "|".join(sorted((re.escape(value) for value in _MONTHS), key=len, reverse=True))

_WEEKDAYS: Final[dict[str, int]] = {
    "monday": 0,
    "lunes": 0,
    "tuesday": 1,
    "martes": 1,
    "wednesday": 2,
    "miércoles": 2,
    "miercoles": 2,
    "thursday": 3,
    "jueves": 3,
    "friday": 4,
    "viernes": 4,
    "saturday": 5,
    "sábado": 5,
    "sabado": 5,
    "sunday": 6,
    "domingo": 6,
}

_NAME_PATTERNS: Final = (
    re.compile(
        r"\b(?:soy|mi nombre es)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{0,59}?)"
        r"(?=\s*(?:,|\.|$|\by\s+mi\s+email\b|\bmi\s+email\b))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i['’]?m|i am|my name is)\s+([A-Za-z][A-Za-z' -]{0,59}?)"
        r"(?=\s*(?:,|\.|$|\band\s+my\s+email\b|\bmy\s+email\b))",
        re.IGNORECASE,
    ),
)

_SUBJECT_PATTERNS: Final = (
    re.compile(r"\b(?:es\s+)?para\s+hablar\s+de\s+(.+?)(?=\s*$)", re.IGNORECASE),
    re.compile(r"\b(?:el\s+)?tema\s+(?:es|ser[ií]a)\s+(.+?)(?=\s*$)", re.IGNORECASE),
    re.compile(r"\bto\s+discuss\s+(.+?)(?=\s*$)", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?topic\s+is\s+(.+?)(?=\s*$)", re.IGNORECASE),
)

_MEETING_RE: Final = re.compile(r"\b(?:reuni[oó]n|reuniones|meeting|meetings|call|llamada)\b", re.IGNORECASE)
_MEETING_REQUEST_RE: Final = re.compile(
    r"\b(?:quiero|quisiera|querr[ií]a|podemos|coordinar|agendar|agendemos|reservar|"
    r"i(?:'|’)d\s+like|i\s+would\s+like|can\s+we|could\s+we|arrange|schedule|book|set\s+up)\b",
    re.IGNORECASE,
)


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


class AmbiguousSchedulingTurn(BaseModel):
    """Minimal semantic fallback. Deterministic fields never go through the model."""

    intent: SchedulingIntent
    visitor_name: str | None = None
    subject: str | None = None


class SchedulingTurnParser:
    """Deterministic-first parser with a tiny LLM fallback for genuine ambiguity."""

    def __init__(
        self,
        llm: LlmPort,
        policy: SchedulingPolicy,
        fallback_config: GenerationConfig,
    ) -> None:
        self._llm = llm
        self._policy = policy
        self._fallback_config = fallback_config

    async def parse(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
    ) -> SchedulingTurn:
        text = user_message.strip()
        now = datetime.now(timezone.utc).astimezone(self._policy.timezone)

        if self._policy.is_explicit_confirmation(text):
            return SchedulingTurn(intent=SchedulingIntent.CONFIRM)
        if self._policy.is_rejection(text):
            return SchedulingTurn(intent=SchedulingIntent.CANCEL)

        email = self._extract_email(text)
        slot_id = self._extract_slot(text)
        start_date, end_date = self._extract_dates(text, now.date())
        visitor_name = self._extract_name(text)
        subject = self._extract_subject(text)

        if slot_id is not None:
            return SchedulingTurn(
                intent=SchedulingIntent.SELECT,
                slot_id=slot_id,
                visitor_name=visitor_name,
                visitor_email=email,
                subject=subject,
            )

        if any(value is not None for value in (start_date, email, visitor_name, subject)):
            return SchedulingTurn(
                intent=SchedulingIntent.INFORM,
                start_date=start_date,
                end_date=end_date,
                visitor_name=visitor_name,
                visitor_email=email,
                subject=subject,
            )

        if _MEETING_RE.search(text) and _MEETING_REQUEST_RE.search(text):
            return SchedulingTurn(intent=SchedulingIntent.REQUEST)

        return await self._semantic_fallback(state, text, relation, now)

    async def _semantic_fallback(
        self,
        state: SessionState,
        user_message: str,
        relation: RouteRelation,
        now: datetime,
    ) -> SchedulingTurn:
        payload = {
            "CURRENT_DATE": now.date().isoformat(),
            "TIMEZONE": self._policy.config.timezone,
            "RELATION": relation.value,
            "OFFERED_SLOT_IDS": list(state.scheduling.offered_slots),
            "VISITOR_MESSAGE": user_message,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify only the latest visitor message for a meeting workflow. "
                    "request=asks to arrange/check a meeting; inform=provides meeting details; "
                    "select=chooses a previously offered slot; confirm=explicitly confirms; "
                    "cancel=cancels; other=not scheduling. Professional questions about work, "
                    "projects, technologies, tools, rates, skills or capabilities are other. "
                    "Python already handles dates, emails, slot numbers and explicit confirmation/cancel. "
                    "Only extract visitor_name for an explicit self-introduction and subject for an "
                    "explicit meeting topic. Do not invent or copy any other state. Return JSON only."
                ),
            },
            {"role": "user", "content": str(payload)},
        ]
        try:
            raw = await self._llm.complete(
                messages,
                self._fallback_config,
                response_schema=AmbiguousSchedulingTurn,
            )
            parsed = AmbiguousSchedulingTurn.model_validate_json(raw)
            intent = parsed.intent
            if parsed.visitor_name or parsed.subject:
                intent = SchedulingIntent.INFORM if intent == SchedulingIntent.OTHER else intent
            return SchedulingTurn(
                intent=intent,
                visitor_name=parsed.visitor_name,
                subject=parsed.subject,
            )
        except Exception:
            return SchedulingTurn(intent=SchedulingIntent.OTHER)

    @staticmethod
    def _extract_email(text: str) -> str | None:
        match = _EMAIL_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _extract_slot(text: str) -> str | None:
        direct = _DIRECT_SLOT_RE.search(text)
        if direct:
            return f"S{int(direct.group(1))}"

        numbered = _NUMBERED_SLOT_RE.search(text)
        if numbered:
            return f"S{int(numbered.group(1))}"

        lowered = text.casefold()
        for word, index in _ORDINALS.items():
            if re.search(rf"(?<!\w){re.escape(word.casefold())}(?!\w)", lowered):
                return f"S{index}"
        return None

    @staticmethod
    def _extract_name(text: str) -> str | None:
        for pattern in _NAME_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip(" ,.")
        return None

    @staticmethod
    def _extract_subject(text: str) -> str | None:
        for pattern in _SUBJECT_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip(" ,.")
        return None

    @classmethod
    def _extract_dates(cls, text: str, today: date) -> tuple[date | None, date | None]:
        lowered = text.casefold()

        if re.search(r"\b(?:pasado\s+mañana|the\s+day\s+after\s+tomorrow)\b", lowered):
            value = today + timedelta(days=2)
            return value, value
        if re.search(r"\b(?:mañana|tomorrow)\b", lowered):
            value = today + timedelta(days=1)
            return value, value

        spanish_range = re.search(
            rf"\bdel\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+de\s+({_MONTH_PATTERN})(?:\s+de\s+(\d{{4}}))?\b",
            lowered,
            re.IGNORECASE,
        )
        if spanish_range:
            month = _MONTHS[spanish_range.group(3).casefold()]
            year = int(spanish_range.group(4) or today.year)
            return cls._safe_date(year, month, int(spanish_range.group(1))), cls._safe_date(
                year,
                month,
                int(spanish_range.group(2)),
            )

        english_range = re.search(
            rf"\bfrom\s+({_MONTH_PATTERN})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\s+to\s+"
            rf"({_MONTH_PATTERN})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b",
            lowered,
            re.IGNORECASE,
        )
        if english_range:
            start_month = _MONTHS[english_range.group(1).casefold()]
            end_month = _MONTHS[english_range.group(4).casefold()]
            end_year = int(english_range.group(6) or today.year)
            start_year = int(english_range.group(3) or end_year)
            return cls._safe_date(start_year, start_month, int(english_range.group(2))), cls._safe_date(
                end_year,
                end_month,
                int(english_range.group(5)),
            )

        spanish_date = re.search(
            rf"\b(?:el\s+)?(\d{{1,2}})\s+de\s+({_MONTH_PATTERN})(?:\s+de\s+(\d{{4}}))?\b",
            lowered,
            re.IGNORECASE,
        )
        if spanish_date:
            value = cls._safe_date(
                int(spanish_date.group(3) or today.year),
                _MONTHS[spanish_date.group(2).casefold()],
                int(spanish_date.group(1)),
            )
            return value, value

        english_date = re.search(
            rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b",
            lowered,
            re.IGNORECASE,
        )
        if english_date:
            value = cls._safe_date(
                int(english_date.group(3) or today.year),
                _MONTHS[english_date.group(1).casefold()],
                int(english_date.group(2)),
            )
            return value, value

        numeric_date = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", lowered)
        if numeric_date:
            year_text = numeric_date.group(3)
            year = today.year if year_text is None else int(year_text)
            if year < 100:
                year += 2000
            value = cls._safe_date(year, int(numeric_date.group(2)), int(numeric_date.group(1)))
            return value, value

        for word, weekday in _WEEKDAYS.items():
            if re.search(rf"(?<!\w){re.escape(word.casefold())}(?!\w)", lowered):
                delta = (weekday - today.weekday()) % 7
                if delta == 0:
                    delta = 7
                value = today + timedelta(days=delta)
                return value, value

        return None, None

    @staticmethod
    def _safe_date(year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None
