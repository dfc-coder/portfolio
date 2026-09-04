from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import PortfolioAgent
from .api import create_router
from .embeddings import Embeddings
from .llm import GenerationConfig, LlamaCpp
from .profile import load_profile
from .search import PortfolioSearch
from .sessions import MemorySessions
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    profile = load_profile(settings.profile_path)

    llm = LlamaCpp(
        settings.llama_base_url,
        settings.llama_model,
        settings.llama_timeout_seconds,
    )
    embeddings = Embeddings(
        settings.embedding_base_url,
        settings.embedding_model,
        settings.embedding_timeout_seconds,
    )
    search = PortfolioSearch(
        profile,
        embeddings,
        max_chars=settings.context_max_chars,
        max_documents=settings.context_max_documents,
        min_score=settings.portfolio_min_score,
    )
    sessions = MemorySessions(settings.session_ttl_seconds, settings.session_max_turns)
    agent = PortfolioAgent(
        profile,
        sessions,
        search,
        llm,
        GenerationConfig(
            temperature=settings.generation_temperature,
            max_tokens=settings.generation_max_tokens,
        ),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await agent.warm()
        yield

    app = FastAPI(title="Portfolio Assistant", version="0.5.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_router(agent))

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        llm_ok, embeddings_ok = await asyncio.gather(llm.health(), embeddings.health())
        return {"ok": llm_ok and embeddings_ok, "llm": llm_ok, "embeddings": embeddings_ok}

    return app


app = create_app()
