from __future__ import annotations

import asyncio

from semantic_router import Route as SemanticRoute
from semantic_router.index.local import LocalIndex
from semantic_router.routers import SemanticRouter as AurelioSemanticRouter

from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain, RouteRelation, RoutingDecision
from app.infrastructure.embeddings.semantic_router import EmbeddingPortEncoder
from app.ports.embeddings import EmbeddingPort

_BUSINESS_UTTERANCES = [
    "¿Cuánto cobra Diego por hora?",
    "¿Qué podés hacer?",
    "¿Podés usar herramientas?",
    "¿Podés agendar reuniones?",
    "¿Podés consultar disponibilidad?",
    "¿Qué proyectos hizo Diego?",
    "¿Diego trabaja con AWS?",
    "¿Tiene experiencia con agentes?",
    "¿Trabaja con APIs e integraciones?",
    "¿Puede trabajar con modelos locales?",
    "¿Qué tecnologías usa?",
    "Contame sobre PocketTrace",
    "Contame sobre el Financial MCP Server",
    "¿Cómo aborda la seguridad en sistemas con LLMs?",
    "What can you do?",
    "Can you use tools?",
    "Can you schedule meetings?",
    "Tell me about Diego's AI work",
    "Does Diego work with distributed systems?",
]

_SCHEDULING_UTTERANCES = [
    "Quiero una reunión el martes",
    "Quiero hablar con Diego la semana que viene",
    "Agendame una reunión con Diego",
    "Consultá disponibilidad para el próximo martes",
    "¿Qué horarios tiene Diego el jueves?",
    "Quiero reservar media hora con Diego",
    "Necesito coordinar una llamada con Diego",
    "Me gustaría reunirme con Diego mañana",
    "Cambiemos la reunión al viernes",
    "Quiero cancelar la reunión con Diego",
    "I'd like to meet Diego next week",
    "Check Diego's availability for Tuesday",
    "Book a meeting with Diego",
    "Can we talk on Thursday afternoon?",
    "I need to reschedule my meeting with Diego",
    "Cancel my meeting with Diego",
]

_SCHEDULING_CONTINUE_UTTERANCES = [
    "El segundo",
    "S2",
    "Mejor el primero",
    "Mi email es ana@example.com",
    "Soy Ana",
    "Es para hablar de arquitectura",
    "Sí, confirmo",
    "No, cancelá",
    "Tuesday could work",
    "Tomorrow instead",
    "The second slot",
    "My email is ana@example.com",
]


class SemanticRouter:
    """Open-set portfolio routing backed by Aurelio semantic-router.

    Only business and scheduling are positive routes. A threshold miss or an
    ambiguous match abstains to GENERAL. During an active scheduling workflow,
    the same pattern distinguishes scheduling continuation from interruptions.
    """

    def __init__(
        self,
        embeddings: EmbeddingPort,
        *,
        business_threshold: float = 0.55,
        scheduling_threshold: float = 0.58,
        continuation_threshold: float = 0.50,
        min_margin: float = 0.05,
    ) -> None:
        self._embeddings = embeddings
        self._encoder = EmbeddingPortEncoder(
            name="portfolio-qwen-semantic-router",
            type="llama_cpp_port",
            embeddings=embeddings,
        )
        self._business_threshold = business_threshold
        self._scheduling_threshold = scheduling_threshold
        self._continuation_threshold = continuation_threshold
        self._min_margin = max(0.0, min_margin)
        self._new_router: AurelioSemanticRouter | None = None
        self._active_router: AurelioSemanticRouter | None = None
        self._warm_lock = asyncio.Lock()

    async def warm(self) -> None:
        if self._new_router is not None and self._active_router is not None:
            return
        async with self._warm_lock:
            if self._new_router is not None and self._active_router is not None:
                return

            probe = await self._embeddings.embed_documents([_BUSINESS_UTTERANCES[0]])
            if not probe or not probe[0]:
                raise ValueError("Embedding service returned an empty routing vector")
            dimensions = len(probe[0])

            new_router = self._empty_router(dimensions)
            await new_router.aadd(
                [
                    SemanticRoute(
                        name="business",
                        utterances=_BUSINESS_UTTERANCES,
                        score_threshold=self._business_threshold,
                    ),
                    SemanticRoute(
                        name="scheduling",
                        utterances=_SCHEDULING_UTTERANCES,
                        score_threshold=self._scheduling_threshold,
                    ),
                ]
            )

            active_router = self._empty_router(dimensions)
            await active_router.aadd(
                [
                    SemanticRoute(
                        name="business_interrupt",
                        utterances=_BUSINESS_UTTERANCES,
                        score_threshold=self._business_threshold,
                    ),
                    SemanticRoute(
                        name="scheduling_continue",
                        utterances=_SCHEDULING_CONTINUE_UTTERANCES,
                        score_threshold=self._continuation_threshold,
                    ),
                ]
            )

            self._new_router = new_router
            self._active_router = active_router

    async def route(self, state: SessionState, user_message: str) -> RoutingDecision:
        await self.warm()
        if state.active_workflow == ActiveWorkflow.SCHEDULING:
            assert self._active_router is not None
            return await self._choose(
                self._active_router,
                user_message,
                {
                    "business_interrupt": (
                        RouteDomain.BUSINESS,
                        RouteRelation.INTERRUPT,
                    ),
                    "scheduling_continue": (
                        RouteDomain.SCHEDULING,
                        RouteRelation.CONTINUE,
                    ),
                },
                no_match_relation=RouteRelation.INTERRUPT,
            )

        assert self._new_router is not None
        return await self._choose(
            self._new_router,
            user_message,
            {
                "business": (RouteDomain.BUSINESS, RouteRelation.NEW),
                "scheduling": (RouteDomain.SCHEDULING, RouteRelation.NEW),
            },
            no_match_relation=RouteRelation.NEW,
        )

    async def route_non_scheduling(
        self,
        state: SessionState,
        user_message: str,
    ) -> RoutingDecision:
        """Reconsider a scheduling false positive without offering scheduling again."""
        await self.warm()
        if state.active_workflow == ActiveWorkflow.SCHEDULING:
            assert self._active_router is not None
            return await self._choose(
                self._active_router,
                user_message,
                {
                    "business_interrupt": (
                        RouteDomain.BUSINESS,
                        RouteRelation.INTERRUPT,
                    )
                },
                no_match_relation=RouteRelation.INTERRUPT,
                route_filter=["business_interrupt"],
            )

        assert self._new_router is not None
        return await self._choose(
            self._new_router,
            user_message,
            {"business": (RouteDomain.BUSINESS, RouteRelation.NEW)},
            no_match_relation=RouteRelation.NEW,
            route_filter=["business"],
        )

    def _empty_router(self, dimensions: int) -> AurelioSemanticRouter:
        return AurelioSemanticRouter(
            encoder=self._encoder,
            routes=[],
            index=LocalIndex(dimensions=dimensions),
            top_k=5,
            aggregation="mean",
            auto_sync=None,
            init_async_index=True,
        )

    async def _choose(
        self,
        router: AurelioSemanticRouter,
        user_message: str,
        route_map: dict[str, tuple[RouteDomain, RouteRelation]],
        *,
        no_match_relation: RouteRelation,
        route_filter: list[str] | None = None,
    ) -> RoutingDecision:
        raw_choices = await router.acall(
            text=user_message,
            limit=2,
            route_filter=route_filter,
        )
        choices = raw_choices if isinstance(raw_choices, list) else [raw_choices]
        choices = [choice for choice in choices if choice.name in route_map]
        choices.sort(
            key=lambda choice: choice.similarity_score or 0.0,
            reverse=True,
        )
        scores = {
            choice.name: float(choice.similarity_score or 0.0)
            for choice in choices
            if choice.name is not None
        }

        if not choices:
            return self._general_decision(
                no_match_relation,
                source="semantic-router:no-match",
                scores=scores,
            )

        if len(choices) > 1:
            first_score = float(choices[0].similarity_score or 0.0)
            second_score = float(choices[1].similarity_score or 0.0)
            if first_score - second_score < self._min_margin:
                return self._general_decision(
                    no_match_relation,
                    source="semantic-router:ambiguous",
                    scores=scores,
                )

        chosen = choices[0]
        assert chosen.name is not None
        domain, relation = route_map[chosen.name]
        confidence = max(0.0, min(1.0, float(chosen.similarity_score or 0.0)))
        return RoutingDecision(
            domain=domain,
            relation=relation,
            route_key=chosen.name,
            confidence=confidence,
            source="semantic-router",
            scores=scores,
        )

    @staticmethod
    def _general_decision(
        relation: RouteRelation,
        *,
        source: str,
        scores: dict[str, float],
    ) -> RoutingDecision:
        return RoutingDecision(
            domain=RouteDomain.GENERAL,
            relation=relation,
            route_key="general_interrupt" if relation == RouteRelation.INTERRUPT else "general",
            confidence=0.0,
            source=source,
            scores=scores,
        )
