from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from .agent import PortfolioAgent
from .api.router import create_router
from .config import Config


def _load_profile(path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict):
        raise ValueError("business profile must be a JSON object")
    return profile


def _client(base_url: str, timeout: float) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key="local",
        timeout=timeout,
    )


def create_app(config: Config | None = None, agent: PortfolioAgent | None = None) -> FastAPI:
    config = config or Config.from_env()
    clients: list[AsyncOpenAI] = []

    if agent is None:
        profile = _load_profile(config.profile_path)
        owner = profile.get("owner")
        if not isinstance(owner, dict) or not isinstance(owner.get("name"), str):
            raise ValueError("business profile is missing owner.name")

        chat = _client(config.llama_base_url, config.llama_timeout_seconds)
        embeddings = _client(config.embedding_base_url, config.embedding_timeout_seconds)
        clients.extend((chat, embeddings))
        agent = PortfolioAgent(
            owner["name"],
            profile,
            chat,
            embeddings,
            chat_model=config.llama_model,
            embedding_model=config.embedding_model,
            temperature=config.generation_temperature,
            max_tokens=config.generation_max_tokens,
            max_chars=config.context_max_chars,
            max_documents=config.context_max_documents,
            min_score=config.portfolio_min_score,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await agent.warm()
        yield
        for client in clients:
            await client.close()

    app = FastAPI(title="Portfolio Assistant", version="0.6.0", lifespan=lifespan)
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

    return app


app = create_app()
