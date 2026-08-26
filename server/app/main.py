from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import create_router
from app.bootstrap import build_runtime
from app.infrastructure.config.settings import Settings
from app.infrastructure.http_security import EdgeSecurityMiddleware
from app.ports.embeddings import EmbeddingPort
from app.ports.llm import LlmPort
from app.scheduling.approval import BookingApproval


def create_app(
    settings: Settings | None = None,
    agent: Any | None = None,
    approvals: BookingApproval | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    llm: LlmPort | None = None
    embeddings: EmbeddingPort | None = None
    if agent is None:
        runtime = build_runtime(resolved)
        agent = runtime.agent
        approvals = runtime.approvals
        llm = runtime.llm
        embeddings = runtime.embeddings

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        warm = getattr(agent, "warm", None)
        if callable(warm):
            await warm()
        yield

    app = FastAPI(
        title="Portfolio Business Representative",
        version="0.5.0",
        lifespan=lifespan,
        docs_url="/docs" if resolved.api_docs_enabled else None,
        redoc_url="/redoc" if resolved.api_docs_enabled else None,
        openapi_url="/openapi.json" if resolved.api_docs_enabled else None,
    )
    app.add_middleware(
        EdgeSecurityMiddleware,
        max_request_bytes=resolved.max_request_bytes,
        requests_per_window=resolved.rate_limit_requests_per_window,
        global_requests_per_window=resolved.global_rate_limit_requests_per_window,
        window_seconds=resolved.rate_limit_window_seconds,
        max_streams_per_client=resolved.max_streams_per_client,
        max_global_streams=resolved.max_global_streams,
        trust_proxy_headers=resolved.trust_proxy_headers,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.allowed_origins),
        allow_credentials=False,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(create_router(agent, approvals))

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready() -> dict[str, str]:
        llama_ready = llm is None or await llm.health()
        embedding_ready = embeddings is None or await embeddings.health()
        if not llama_ready or not embedding_ready:
            return {
                "status": "degraded",
                "llama": "ready" if llama_ready else "unavailable",
                "embedding": "ready" if embedding_ready else "unavailable",
            }
        return {
            "status": "ok",
            "llama": "ready",
            "embedding": "ready",
        }

    return app


app = create_app()
