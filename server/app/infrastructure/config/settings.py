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
    planner_temperature: float = 0.0
    planner_max_tokens: int = 64
    renderer_temperature: float = 0.65
    renderer_max_tokens: int = 180
    reranker_base_url: str = "http://reranker:8081"
    reranker_model: str = "Qwen3-Reranker-0.6B-Q8_0"
    reranker_timeout_seconds: float = 30.0
    router_min_score: float = 0.10
    router_min_margin: float = 0.08
    router_judge_temperature: float = 0.0
    router_judge_max_tokens: int = 32

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[3]
        return cls(
            profile_path=Path(
                os.getenv("BUSINESS_PROFILE_PATH", root / "config" / "business-profile.json")
            ),
            llama_base_url=os.getenv("LLAMA_BASE_URL", "http://llama:8080").rstrip("/"),
            llama_model=os.getenv("LLAMA_MODEL", "Qwen3.5-2B"),
            llama_timeout_seconds=float(os.getenv("LLAMA_TIMEOUT_SECONDS", "90")),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "1800")),
            session_max_turns=int(os.getenv("SESSION_MAX_TURNS", "8")),
            allowed_origins=_csv(
                os.getenv(
                    "ALLOWED_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173",
                )
            ),
            calendar_mode=os.getenv("CALENDAR_MODE", "mock").lower(),
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            google_refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            planner_temperature=float(os.getenv("PLANNER_TEMPERATURE", "0.0")),
            planner_max_tokens=int(os.getenv("PLANNER_MAX_TOKENS", "64")),
            renderer_temperature=float(os.getenv("RENDERER_TEMPERATURE", "0.65")),
            renderer_max_tokens=int(os.getenv("RENDERER_MAX_TOKENS", "180")),
            reranker_base_url=os.getenv("RERANKER_BASE_URL", "http://reranker:8081").rstrip("/"),
            reranker_model=os.getenv("RERANKER_MODEL", "Qwen3-Reranker-0.6B-Q8_0"),
            reranker_timeout_seconds=float(os.getenv("RERANKER_TIMEOUT_SECONDS", "30")),
            router_min_score=float(os.getenv("ROUTER_MIN_SCORE", "0.10")),
            router_min_margin=float(os.getenv("ROUTER_MIN_MARGIN", "0.08")),
            router_judge_temperature=float(os.getenv("ROUTER_JUDGE_TEMPERATURE", "0.0")),
            router_judge_max_tokens=int(os.getenv("ROUTER_JUDGE_MAX_TOKENS", "32")),
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
