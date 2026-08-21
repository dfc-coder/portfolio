from __future__ import annotations

from app.agent.belief import BeliefUpdater
from app.agent.capability_executor import CapabilityExecutor
from app.agent.capability_registry import CapabilityRegistry
from app.agent.context import ContextBuilder
from app.agent.interpreter import SchedulingInterpreter
from app.agent.loop import BoundedCapabilityLoop
from app.agent.renderer import HybridRenderer
from app.agent.representative import BusinessRepresentative
from app.agent.safety import CapabilitySafetyGate
from app.agent.selector import CapabilitySelector
from app.agent.semantic_router import CascadingSemanticRouter
from app.agent.verifier import AgentVerifier
from app.infrastructure.calendar.google import GoogleCalendarGateway
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.infrastructure.reranker.llama_cpp import LlamaCppReranker
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


def build_agent(settings: Settings) -> tuple[BusinessRepresentative, LlamaCppClient, LlamaCppReranker]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore(settings.session_ttl_seconds, settings.session_max_turns)
    calendar = GoogleCalendarGateway(settings) if settings.calendar_mode == "google" else InMemoryCalendarGateway()
    slots = SlotService(calendar, policy)

    llm = LlamaCppClient(settings.llama_base_url, settings.llama_model, settings.llama_timeout_seconds)
    reranker = LlamaCppReranker(settings.reranker_base_url, settings.reranker_model, settings.reranker_timeout_seconds)

    interpreter_config = GenerationConfig(
        temperature=settings.planner_temperature,
        max_tokens=settings.planner_max_tokens,
        top_p=0.9,
        top_k=20,
    )
    renderer_config = GenerationConfig(
        temperature=settings.renderer_temperature,
        max_tokens=settings.renderer_max_tokens,
        top_p=0.9,
        top_k=20,
    )
    repair_config = GenerationConfig(
        temperature=settings.repair_temperature,
        max_tokens=settings.repair_max_tokens,
        top_p=0.9,
        top_k=20,
    )
    judge_config = GenerationConfig(
        temperature=settings.router_judge_temperature,
        max_tokens=settings.router_judge_max_tokens,
        top_p=0.8,
        top_k=10,
    )

    router = CascadingSemanticRouter(
        reranker,
        llm,
        judge_config,
        min_score=settings.router_min_score,
        min_margin=settings.router_min_margin,
    )
    interpreter = SchedulingInterpreter(llm, policy, interpreter_config)
    belief = BeliefUpdater()
    registry = CapabilityRegistry()
    selector = CapabilitySelector(
        reranker,
        llm,
        judge_config,
        min_margin=settings.router_min_margin,
    )
    safety = CapabilitySafetyGate(policy)
    capability_executor = CapabilityExecutor(slots, calendar, policy)
    loop = BoundedCapabilityLoop(
        belief,
        registry,
        selector,
        safety,
        capability_executor,
        max_steps=settings.agent_max_steps,
        max_repairs=settings.agent_max_repairs,
    )
    renderer = HybridRenderer(llm, ContextBuilder(profile, policy), renderer_config, repair_config)
    representative = BusinessRepresentative(
        sessions,
        policy,
        router,
        interpreter,
        belief,
        loop,
        AgentVerifier(),
        renderer,
    )
    return representative, llm, reranker
