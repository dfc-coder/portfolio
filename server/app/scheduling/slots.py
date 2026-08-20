from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.domain.scheduling import BusyInterval, OfferedSlot
from app.ports.calendar import CalendarPort

from .policy import SchedulingPolicy

_DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class SlotService:
    def __init__(self, calendar: CalendarPort, policy: SchedulingPolicy) -> None:
        self._calendar = calendar
        self._policy = policy

    async def available_slots(
        self,
        start_date: date,
        end_date: date,
        now: datetime | None = None,
    ) -> list[OfferedSlot]:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")

        current = now or datetime.now(timezone.utc)
        tz = self._policy.timezone
        local_now = current.astimezone(tz)
        max_date = (local_now + timedelta(days=self._policy.config.max_days_ahead)).date()
        end_date = min(end_date, max_date)

        query_start = datetime.combine(start_date, time.min, tzinfo=tz)
        query_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        busy = await self._calendar.busy_intervals(query_start, query_end, self._policy.config.timezone)

        slots: list[OfferedSlot] = []
        day = start_date
        duration = timedelta(minutes=self._policy.config.meeting_minutes)
        min_start = local_now + timedelta(hours=self._policy.config.min_notice_hours)

        while day <= end_date and len(slots) < self._policy.config.max_slots:
            hours = self._policy.config.business_hours.get(_DAY_NAMES[day.weekday()])
            if hours:
                day_start = datetime.combine(day, hours[0], tzinfo=tz)
                day_end = datetime.combine(day, hours[1], tzinfo=tz)
                cursor = day_start
                while cursor + duration <= day_end and len(slots) < self._policy.config.max_slots:
                    candidate = OfferedSlot(start=cursor, end=cursor + duration)
                    if candidate.start >= min_start and not self._conflicts(candidate, busy):
                        slots.append(candidate)
                    cursor += duration
            day += timedelta(days=1)

        return slots

    def _conflicts(self, slot: OfferedSlot, busy: list[BusyInterval]) -> bool:
        buffer = timedelta(minutes=self._policy.config.buffer_minutes)
        buffered_start = slot.start - buffer
        buffered_end = slot.end + buffer
        for interval in busy:
            busy_start = interval.start.astimezone(slot.start.tzinfo)
            busy_end = interval.end.astimezone(slot.start.tzinfo)
            if buffered_start < busy_end and buffered_end > busy_start:
                return True
        return False
