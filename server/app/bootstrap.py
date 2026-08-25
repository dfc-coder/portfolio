from __future__ import annotations

from dataclasses import dataclass

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.router import SemanticRouter
from app.agent.scheduler import Scheduler
from app.infrastructure.calendar.google import GoogleCalendarGateway
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.infrastructure.pockettrace import PocketTraceRecorder
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.approval import BookingApproval
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


@dataclass(frozen=True)
class AgentRuntime:
    agent: BusinessRepresentative
    approvals: BookingApproval
    llm: LlamaCppClient
    embeddings: LlamaCppEmbeddingClient


def build_runtime(settings: Settings) -> AgentRuntime:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore(
        settings.session_ttl_seconds,
        settings.session_max_turns,
    )
    calendar = (
        GoogleCalendarGateway(settings)
        if settings.calendar_mode == "google"
        else InMemoryCalendarGateway()
    )
    slots = SlotService(calendar, policy)

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

    interpreter_config = GenerationConfig(
        temperature=0.0,
        max_tokens=min(settings.planner_max_tokens, 64),
        top_p=1.0,
        top_k=1,
    )
    renderer_config = GenerationConfig(
        temperature=settings.renderer_temperature,
        max_tokens=settings.renderer_max_tokens,
        top_p=0.9,
        top_k=20,
    )

    router = SemanticRouter(
        embeddings,
        business_threshold=settings.router_business_threshold,
        scheduling_threshold=settings.router_scheduling_threshold,
        continuation_threshold=settings.router_continuation_threshold,
        min_margin=settings.router_min_margin,
    )
    scheduler = Scheduler(
        llm,
        slots,
        calendar,
        policy,
        interpreter_config,
    )
    responder = Responder(
        llm,
        profile,
        policy,
        renderer_config,
        scheduler.public_capabilities,
        embeddings,
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
        router,
        scheduler,
        responder,
        trace_recorder,
    )
    approvals = BookingApproval(sessions, calendar, policy)
    return AgentRuntime(
        agent=representative,
        approvals=approvals,
        llm=llm,
        embeddings=embeddings,
    )


def build_agent(
    settings: Settings,
) -> tuple[BusinessRepresentative, LlamaCppClient, LlamaCppEmbeddingClient]:
    """Compatibility helper for callers that only need the conversational agent."""
    runtime = build_runtime(settings)
    return runtime.agent, runtime.llm, runtime.embeddings
