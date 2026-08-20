from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import BusinessRepresentative
from .api import create_router
from .calendar_gateway import GoogleCalendarGateway, InMemoryCalendarGateway
from .llama_client import LlamaClient
from .policies import SchedulingPolicy
from .profile import load_business_profile
from .session import SessionStore
from .settings import Settings
from .slot_service import SlotService


def build_agent(settings: Settings) -> tuple[BusinessRepresentative, LlamaClient]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    sessions = SessionStore(settings.session_ttl_seconds, settings.session_max_turns)
    calendar = (
        GoogleCalendarGateway(settings)
        if settings.calendar_mode == "google"
        else InMemoryCalendarGateway()
    )
    slots = SlotService(calendar, policy)
    llama = LlamaClient(
        settings.llama_base_url,
        settings.llama_model,
        settings.llama_timeout_seconds,
    )
    return BusinessRepresentative(profile, sessions, policy, slots, calendar, llama), llama


def create_app(
    settings: Settings | None = None,
    agent: BusinessRepresentative | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    llama: LlamaClient | None = None
    if agent is None:
        agent, llama = build_agent(resolved)

    app = FastAPI(title="Portfolio Business Representative", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.allowed_origins),
        allow_credentials=False,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(create_router(agent))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        if llama is not None and not await llama.health():
            return {"status": "degraded", "llama": "unavailable"}
        return {"status": "ok", "llama": "ready"}

    return app


app = create_app()
