from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx

from app.domain.scheduling import BookingResult, BusyInterval, PendingBooking
from app.infrastructure.config.settings import Settings

from .oauth import GoogleOAuthTokenProvider


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
            "extendedProperties": {
                "private": {"businessRepresentativeBookingId": booking.booking_id}
            },
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
