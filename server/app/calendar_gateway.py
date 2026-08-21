from app.domain.scheduling import BookingResult, BusyInterval
from app.infrastructure.calendar.google import GoogleCalendarGateway
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.calendar.oauth import GoogleOAuthTokenProvider
from app.ports.calendar import CalendarPort

CalendarGateway = CalendarPort

__all__ = [
    "BookingResult",
    "BusyInterval",
    "CalendarGateway",
    "GoogleCalendarGateway",
    "GoogleOAuthTokenProvider",
    "InMemoryCalendarGateway",
]
