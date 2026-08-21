from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import create_router
from app.bootstrap import build_agent
from app.infrastructure.config.settings import Settings
from app.ports.llm import LlmPort
from app.ports.reranker import RerankerPort


def create_app(
    settings: Settings | None = None,
    agent: Any | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    llm: LlmPort | None = None
    reranker: RerankerPort | None = None
    if agent is None:
        agent, llm, reranker = build_agent(resolved)

    app = FastAPI(title="Portfolio Business Representative", version="0.3.0")
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
        llama_ready = llm is None or await llm.health()
        reranker_ready = reranker is None or await reranker.health()
        if not llama_ready or not reranker_ready:
            return {
                "status": "degraded",
                "llama": "ready" if llama_ready else "unavailable",
                "reranker": "ready" if reranker_ready else "unavailable",
            }
        return {"status": "ok", "llama": "ready", "reranker": "ready"}

    return app


app = create_app()
