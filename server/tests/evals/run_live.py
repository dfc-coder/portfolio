from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.router import SemanticRouter
from app.agent.scheduler import Scheduler
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteDomain
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.infrastructure.reranker.llama_cpp import LlamaCppReranker
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


ROUTE_DOMAINS = {
    "business": RouteDomain.BUSINESS,
    "scheduling": RouteDomain.SCHEDULING,
    "general": RouteDomain.GENERAL,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the real reranker + SLM stack.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases.jsonl"),
    )
    parser.add_argument("--critical-repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return cases


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def configure_scheduling_state(state: SessionState, stage: str | None) -> None:
    if not stage:
        return

    start = datetime.now(timezone.utc) + timedelta(days=7)
    first = OfferedSlot(start=start, end=start + timedelta(minutes=30))
    second = OfferedSlot(
        start=start + timedelta(minutes=45),
        end=start + timedelta(minutes=75),
    )

    if stage in {"scheduling_slot", "scheduling_details", "scheduling_confirmation"}:
        state.scheduling.offered_slots = {"S1": first, "S2": second}

    if stage in {"scheduling_details", "scheduling_confirmation"}:
        state.scheduling.selected_slot_id = "S1"

    if stage == "scheduling_confirmation":
        state.scheduling.visitor_name = "Ana"
        state.scheduling.visitor_email = "ana@example.com"
        state.scheduling.subject = "Architecture discussion"
        state.scheduling.pending_booking = PendingBooking(
            booking_id="eval-booking",
            slot=first,
            visitor_name="Ana",
            visitor_email="ana@example.com",
            subject="Architecture discussion",
        )


def state_for_case(case: dict[str, Any], repetition: int) -> SessionState:
    state = SessionState(session_id=f"eval-{case.get('id', 'case')}-{repetition}")
    raw_state = case.get("state") or {}
    if raw_state.get("active_workflow") == "scheduling":
        state.active_workflow = ActiveWorkflow.SCHEDULING
        configure_scheduling_state(state, raw_state.get("stage"))
    return state


def build_router(
    settings: Settings,
    llm: LlamaCppClient,
    reranker: LlamaCppReranker,
) -> SemanticRouter:
    return SemanticRouter(
        reranker,
        llm,
        GenerationConfig(
            temperature=settings.router_judge_temperature,
            max_tokens=settings.router_judge_max_tokens,
            top_p=0.8,
            top_k=10,
        ),
        min_score=settings.router_min_score,
        min_margin=settings.router_min_margin,
    )


def build_eval_agent(
    settings: Settings,
    llm: LlamaCppClient,
    reranker: LlamaCppReranker,
) -> tuple[BusinessRepresentative, MemorySessionStore, InMemoryCalendarGateway]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore(settings.session_ttl_seconds, settings.session_max_turns)
    calendar = InMemoryCalendarGateway()
    slots = SlotService(calendar, policy)
    router = build_router(settings, llm, reranker)
    scheduler = Scheduler(
        llm,
        slots,
        calendar,
        policy,
        GenerationConfig(
            temperature=settings.planner_temperature,
            max_tokens=settings.planner_max_tokens,
            top_p=0.9,
            top_k=20,
        ),
    )
    responder = Responder(
        llm,
        profile,
        policy,
        GenerationConfig(
            temperature=settings.renderer_temperature,
            max_tokens=settings.renderer_max_tokens,
            top_p=0.9,
            top_k=20,
        ),
        scheduler.public_capabilities,
    )
    return BusinessRepresentative(sessions, router, scheduler, responder), sessions, calendar


def route_key_domain(route_key: str) -> str:
    if route_key.startswith("business"):
        return "business"
    if route_key.startswith("scheduling"):
        return "scheduling"
    return "general"


async def evaluate_routing(
    cases: list[dict[str, Any]],
    router: SemanticRouter,
    critical_repetitions: int,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    by_case: dict[str, list[bool]] = defaultdict(list)

    for case in cases:
        if case.get("kind") != "routing":
            continue
        repetitions = critical_repetitions if case.get("critical") else 1
        for repetition in range(repetitions):
            state = state_for_case(case, repetition)
            started = time.perf_counter()
            decision = await router.route(state, case["message"])
            latency_ms = (time.perf_counter() - started) * 1000
            expected_domain = case["domain"]
            expected_relation = case["relation"]
            correct = (
                decision.domain.value == expected_domain
                and decision.relation.value == expected_relation
            )
            case_id = case.get("id", case["message"])
            by_case[case_id].append(correct)

            ranked_scores = sorted(decision.scores.items(), key=lambda item: item[1], reverse=True)
            top_score = ranked_scores[0][1] if ranked_scores else 0.0
            second_score = ranked_scores[1][1] if len(ranked_scores) > 1 else 0.0
            top_domain = route_key_domain(ranked_scores[0][0]) if ranked_scores else None

            records.append(
                {
                    "case_id": case_id,
                    "message": case["message"],
                    "critical": bool(case.get("critical")),
                    "expected_domain": expected_domain,
                    "expected_relation": expected_relation,
                    "actual_domain": decision.domain.value,
                    "actual_relation": decision.relation.value,
                    "source": decision.source,
                    "scores": decision.scores,
                    "top_domain": top_domain,
                    "top_score": top_score,
                    "margin": top_score - second_score,
                    "latency_ms": round(latency_ms, 2),
                    "correct": correct,
                }
            )

    total = len(records)
    correct_count = sum(record["correct"] for record in records)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        confusion[record["expected_domain"]][record["actual_domain"]] += 1

    non_scheduling = [
        record for record in records if record["expected_domain"] != "scheduling"
    ]
    false_scheduling = [
        record for record in non_scheduling if record["actual_domain"] == "scheduling"
    ]
    judge_attempts = [
        record
        for record in records
        if record["source"] in {"llm_judge", "reranker_fallback", "safe_fallback"}
    ]
    successful_judges = [
        record for record in judge_attempts if record["source"] == "llm_judge"
    ]
    latencies = [record["latency_ms"] for record in records]
    critical_cases = {
        case_id: outcomes
        for case_id, outcomes in by_case.items()
        if any(record["case_id"] == case_id and record["critical"] for record in records)
    }

    return {
        "runs": total,
        "accuracy": round(correct_count / total, 4) if total else 0.0,
        "false_scheduling_rate": (
            round(len(false_scheduling) / len(non_scheduling), 4)
            if non_scheduling
            else 0.0
        ),
        "confusion_matrix": {
            expected: dict(counts) for expected, counts in sorted(confusion.items())
        },
        "source_counts": dict(Counter(record["source"] for record in records)),
        "judge_schema_success_rate": (
            round(len(successful_judges) / len(judge_attempts), 4)
            if judge_attempts
            else 1.0
        ),
        "critical_pass_k": {
            "passed": sum(all(outcomes) for outcomes in critical_cases.values()),
            "total": len(critical_cases),
            "k": critical_repetitions,
        },
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "calibration": calibration_summary(records),
        "failures": [record for record in records if not record["correct"]],
    }


def calibration_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for min_score in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40):
        for min_margin in (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20):
            covered = [
                record
                for record in records
                if record["scores"]
                and record["top_score"] >= min_score
                and record["margin"] >= min_margin
            ]
            if not covered:
                continue
            correct = sum(
                record["top_domain"] == record["expected_domain"] for record in covered
            )
            false_scheduling = sum(
                record["top_domain"] == "scheduling"
                and record["expected_domain"] != "scheduling"
                for record in covered
            )
            candidates.append(
                {
                    "min_score": min_score,
                    "min_margin": min_margin,
                    "coverage": round(len(covered) / len(records), 4),
                    "covered_accuracy": round(correct / len(covered), 4),
                    "false_scheduling": false_scheduling,
                }
            )

    candidates.sort(
        key=lambda item: (
            item["false_scheduling"],
            -item["covered_accuracy"],
            -item["coverage"],
        )
    )
    return candidates[:10]


async def evaluate_conversations(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: LlamaCppClient,
    reranker: LlamaCppReranker,
    critical_repetitions: int,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    by_case: dict[str, list[bool]] = defaultdict(list)

    for case in cases:
        if case.get("kind") != "conversation":
            continue
        repetitions = critical_repetitions if case.get("critical") else 1
        for repetition in range(repetitions):
            agent, sessions, calendar = build_eval_agent(settings, llm, reranker)
            session_id = f"live-{case['id']}-{repetition}"
            started = time.perf_counter()
            error: str | None = None
            try:
                for user_message in case["turns"]:
                    _ = "".join(
                        [chunk async for chunk in agent.respond(session_id, user_message)]
                    )
            except Exception as exc:  # noqa: BLE001 - eval must report model/runtime failures
                error = f"{type(exc).__name__}: {exc}"

            state = await sessions.get(session_id)
            booking_count = len(calendar.bookings)
            active_workflow = state.active_workflow.value if state.active_workflow else None
            expected_booking_count = int(case.get("expected_booking_count", 0))
            expected_active_workflow = case.get("expected_active_workflow")
            correct = (
                error is None
                and booking_count == expected_booking_count
                and active_workflow == expected_active_workflow
            )
            latency_ms = (time.perf_counter() - started) * 1000
            by_case[case["id"]].append(correct)
            records.append(
                {
                    "case_id": case["id"],
                    "critical": bool(case.get("critical")),
                    "turns": case["turns"],
                    "expected_booking_count": expected_booking_count,
                    "actual_booking_count": booking_count,
                    "expected_active_workflow": expected_active_workflow,
                    "actual_active_workflow": active_workflow,
                    "latency_ms": round(latency_ms, 2),
                    "error": error,
                    "correct": correct,
                }
            )

    latencies = [record["latency_ms"] for record in records]
    critical_cases = {
        case_id: outcomes
        for case_id, outcomes in by_case.items()
        if any(record["case_id"] == case_id and record["critical"] for record in records)
    }
    unexpected_side_effects = sum(
        record["expected_booking_count"] == 0 and record["actual_booking_count"] > 0
        for record in records
    )

    return {
        "runs": len(records),
        "pass_rate": (
            round(sum(record["correct"] for record in records) / len(records), 4)
            if records
            else 1.0
        ),
        "unexpected_calendar_writes": unexpected_side_effects,
        "critical_pass_k": {
            "passed": sum(all(outcomes) for outcomes in critical_cases.values()),
            "total": len(critical_cases),
            "k": critical_repetitions,
        },
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "failures": [record for record in records if not record["correct"]],
    }


async def main() -> int:
    args = parse_args()
    if args.critical_repetitions < 1:
        raise ValueError("--critical-repetitions must be >= 1")

    settings = Settings.from_env()
    cases = load_cases(args.cases)

    async with (
        httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as llm_http,
        httpx.AsyncClient(timeout=settings.reranker_timeout_seconds) as reranker_http,
    ):
        llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=llm_http,
        )
        reranker = LlamaCppReranker(
            settings.reranker_base_url,
            settings.reranker_model,
            settings.reranker_timeout_seconds,
            client=reranker_http,
        )

        health = {
            "llm": await llm.health(),
            "reranker": await reranker.health(),
        }
        if not all(health.values()):
            report = {"health": health, "error": "Required live model service is not ready."}
            rendered = json.dumps(report, ensure_ascii=False, indent=2)
            print(rendered)
            return 2

        router = build_router(settings, llm, reranker)
        routing = await evaluate_routing(
            cases,
            router,
            args.critical_repetitions,
        )
        conversations = await evaluate_conversations(
            cases,
            settings,
            llm,
            reranker,
            args.critical_repetitions,
        )

    report = {
        "health": health,
        "config": {
            "router_min_score": settings.router_min_score,
            "router_min_margin": settings.router_min_margin,
            "critical_repetitions": args.critical_repetitions,
        },
        "dataset": {
            "routing_cases": sum(case.get("kind") == "routing" for case in cases),
            "conversation_cases": sum(case.get("kind") == "conversation" for case in cases),
        },
        "routing": routing,
        "conversations": conversations,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")

    failed = (
        routing["accuracy"] < 1.0
        or conversations["pass_rate"] < 1.0
        or conversations["unexpected_calendar_writes"] > 0
    )
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
