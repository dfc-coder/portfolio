from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    profile_path: Path
    llama_base_url: str
    llama_model: str
    llama_timeout_seconds: float
    session_ttl_seconds: int
    session_max_turns: int
    allowed_origins: tuple[str, ...]
    calendar_mode: str
    google_calendar_id: str
    google_client_id: str | None
    google_client_secret: str | None
    google_refresh_token: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[1]
        return cls(
            profile_path=Path(
                os.getenv("BUSINESS_PROFILE_PATH", root / "config" / "business-profile.json")
            ),
            llama_base_url=os.getenv("LLAMA_BASE_URL", "http://llama:8080").rstrip("/"),
            llama_model=os.getenv("LLAMA_MODEL", "Qwen3.5-2B-Q4_K_XL"),
            llama_timeout_seconds=float(os.getenv("LLAMA_TIMEOUT_SECONDS", "90")),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "1800")),
            session_max_turns=int(os.getenv("SESSION_MAX_TURNS", "12")),
            allowed_origins=_csv(
                os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
            ),
            calendar_mode=os.getenv("CALENDAR_MODE", "mock").lower(),
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            google_refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        )

    def validate_calendar(self) -> None:
        if self.calendar_mode != "google":
            return
        missing = [
            name
            for name, value in (
                ("GOOGLE_CLIENT_ID", self.google_client_id),
                ("GOOGLE_CLIENT_SECRET", self.google_client_secret),
                ("GOOGLE_REFRESH_TOKEN", self.google_refresh_token),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Google Calendar credentials: {', '.join(missing)}")
