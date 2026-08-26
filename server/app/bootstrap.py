from __future__ import annotations

from dataclasses import dataclass

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.infrastructure.pockettrace import PocketTraceRecorder
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig


@dataclass(frozen=True)
class AgentRuntime:
    agent: BusinessRepresentative
    llm: LlamaCppClient
    embeddings: LlamaCppEmbeddingClient


def build_runtime(settings: Settings) -> AgentRuntime:
    profile = load_business_profile(settings.profile_path)
    sessions = MemorySessionStore(
        settings.session_ttl_seconds,
        settings.session_max_turns,
    )

    llm = LlamaCppClient(
        settings.llama_base_url,
        settings.llama_model,
        settings.llama_timeout_seconds,
    )
    embeddings = LlamaCppEmbeddingClient(
        settings.embedding_base_url,
        settings.embedding_model,
        settings.embedding_timeout_seconds,
    )

    renderer_config = GenerationConfig(
        temperature=settings.renderer_temperature,
        max_tokens=settings.renderer_max_tokens,
        top_p=0.9,
        top_k=20,
    )

    responder = Responder(
        llm,
        profile,
        renderer_config,
        embeddings,
        knowledge_min_score=settings.knowledge_relevance_threshold,
        context_max_chars=settings.context_max_chars,
        context_max_documents=settings.context_max_documents,
    )
    trace_recorder = (
        PocketTraceRecorder(
            settings.pockettrace_url,
            settings.llama_model,
            timeout_seconds=settings.pockettrace_timeout_seconds,
        )
        if settings.pockettrace_enabled
        else None
    )
    representative = BusinessRepresentative(
        sessions,
        responder,
        trace_recorder,
    )
    return AgentRuntime(
        agent=representative,
        llm=llm,
        embeddings=embeddings,
    )


def build_agent(
    settings: Settings,
) -> tuple[BusinessRepresentative, LlamaCppClient, LlamaCppEmbeddingClient]:
    runtime = build_runtime(settings)
    return runtime.agent, runtime.llm, runtime.embeddings
