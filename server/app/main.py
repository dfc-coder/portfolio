from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import PortfolioAgent
from .api.router import create_router
from .config import Config
from .embeddings import Embeddings
from .llm import GenerationConfig, LlamaCpp
from .search import PortfolioSearch
from .sessions import MemorySessions


def _load_profile(path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict):
        raise ValueError("business profile must be a JSON object")
    return profile


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    profile = _load_profile(config.profile_path)
    owner = profile.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str):
        raise ValueError("business profile is missing owner.name")

    llm = LlamaCpp(config.llama_base_url, config.llama_model, config.llama_timeout_seconds)
    embeddings = Embeddings(
        config.embedding_base_url,
        config.embedding_model,
        config.embedding_timeout_seconds,
    )
    search = PortfolioSearch(
        profile,
        embeddings,
        max_chars=config.context_max_chars,
        max_documents=config.context_max_documents,
        min_score=config.portfolio_min_score,
    )
    agent = PortfolioAgent(
        owner["name"],
        MemorySessions(config.session_ttl_seconds, config.session_max_turns),
        search,
        llm,
        GenerationConfig(
            temperature=config.generation_temperature,
            max_tokens=config.generation_max_tokens,
        ),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await agent.warm()
        yield

    app = FastAPI(title="Portfolio Assistant", version="0.5.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
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
