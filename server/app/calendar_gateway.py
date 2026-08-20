from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote

import httpx

from .session import PendingBooking
from .settings import Settings


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class BookingResult:
    booking_id: str
    event_id: str
    html_link: str | None
    start: datetime
    end: datetime


class CalendarGateway(Protocol):
    async def busy_intervals(self, start: datetime, end: datetime, timezone_name: str) -> list[BusyInterval]: ...

    async def create_booking(self, booking: PendingBooking, timezone_name: str) -> BookingResult: ...


class GoogleOAuthTokenProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> None:
        self._client = client
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        async with self._lock:
            if self._access_token and time.monotonic() < self._expires_at - 60:
                return self._access_token

            response = await self._client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
            self._access_token = payload["access_token"]
            self._expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
            return self._access_token


class GoogleCalendarGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        settings.validate_calendar()
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._tokens = GoogleOAuthTokenProvider(
            self._client,
            settings.google_client_id or "",
            settings.google_client_secret or "",
            settings.google_refresh_token or "",
        )

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._tokens.access_token()}"}

    async def busy_intervals(
        self,
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> list[BusyInterval]:
        response = await self._client.post(
            "https://www.googleapis.com/calendar/v3/freeBusy",
            headers=await self._headers(),
            json={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "timeZone": timezone_name,
                "items": [{"id": self._settings.google_calendar_id}],
            },
        )
        response.raise_for_status()
        calendar = response.json().get("calendars", {}).get(self._settings.google_calendar_id, {})
        return [
            BusyInterval(
                start=datetime.fromisoformat(item["start"].replace("Z", "+00:00")),
                end=datetime.fromisoformat(item["end"].replace("Z", "+00:00")),
            )
            for item in calendar.get("busy", [])
        ]

    async def create_booking(self, booking: PendingBooking, timezone_name: str) -> BookingResult:
        event_id = f"br{booking.booking_id.replace('-', '')}"
        calendar_id = quote(self._settings.google_calendar_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        payload = {
            "id": event_id,
            "summary": booking.subject,
            "description": "Scheduled through the portfolio business representative.",
            "start": {"dateTime": booking.slot.start.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": booking.slot.end.isoformat(), "timeZone": timezone_name},
            "attendees": [
                {"email": booking.visitor_email, "displayName": booking.visitor_name},
            ],
            "extendedProperties": {"private": {"businessRepresentativeBookingId": booking.booking_id}},
        }
        headers = await self._headers()
        response = await self._client.post(
            url,
            headers=headers,
            params={"sendUpdates": "all"},
            json=payload,
        )

        if response.status_code == 409:
            response = await self._client.get(f"{url}/{event_id}", headers=headers)

        response.raise_for_status()
        event = response.json()
        return BookingResult(
            booking_id=booking.booking_id,
            event_id=event["id"],
            html_link=event.get("htmlLink"),
            start=booking.slot.start,
            end=booking.slot.end,
        )


class InMemoryCalendarGateway:
    def __init__(self, busy: list[BusyInterval] | None = None) -> None:
        self.busy = busy or []
        self.bookings: dict[str, BookingResult] = {}

    async def busy_intervals(
        self,
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> list[BusyInterval]:
        del timezone_name
        return [item for item in self.busy if item.start < end and item.end > start]

    async def create_booking(self, booking: PendingBooking, timezone_name: str) -> BookingResult:
        del timezone_name
        existing = self.bookings.get(booking.booking_id)
        if existing:
            return existing
        result = BookingResult(
            booking_id=booking.booking_id,
            event_id=f"mock-{booking.booking_id}",
            html_link=None,
            start=booking.slot.start.astimezone(timezone.utc),
            end=booking.slot.end.astimezone(timezone.utc),
        )
        self.bookings[booking.booking_id] = result
        return result
