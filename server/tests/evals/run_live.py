from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import httpx

from app.agent.representative import BusinessRepresentative
from app.agent.responder import Responder
from app.agent.router import SemanticRouter
from app.agent.scheduler import Scheduler
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.infrastructure.sessions.memory import MemorySessionStore
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the real embedding + SLM stack.")
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


def build_router(embeddings: LlamaCppEmbeddingClient) -> SemanticRouter:
    return SemanticRouter(embeddings)


def build_eval_agent(
    settings: Settings,
    llm: LlamaCppClient,
    embeddings: LlamaCppEmbeddingClient,
) -> tuple[BusinessRepresentative, MemorySessionStore, InMemoryCalendarGateway]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    sessions = MemorySessionStore(settings.session_ttl_seconds, settings.session_max_turns)
    calendar = InMemoryCalendarGateway()
    slots = SlotService(calendar, policy)
    router = build_router(embeddings)
    scheduler = Scheduler(
        llm,
        slots,
        calendar,
        policy,
        GenerationConfig(
            temperature=settings.planner_temperature,
            max_tokens=settings.planner_max_tokens,
            top_p=1.0,
            top_k=1,
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
        embeddings,
        context_max_chars=settings.context_max_chars,
        context_max_documents=settings.context_max_documents,
    )
    return BusinessRepresentative(sessions, router, scheduler, responder), sessions, calendar


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
            from app.domain.conversation import ActiveWorkflow, SessionState

            state = SessionState(session_id=f"eval-{case.get('id', 'case')}-{repetition}")
            if (case.get("state") or {}).get("active_workflow") == "scheduling":
                state.active_workflow = ActiveWorkflow.SCHEDULING

            started = time.perf_counter()
            decision = await router.route(state, case["message"])
            latency_ms = (time.perf_counter() - started) * 1000
            correct = (
                decision.domain.value == case["domain"]
                and decision.relation.value == case["relation"]
            )
            case_id = case.get("id", case["message"])
            by_case[case_id].append(correct)
            ranked_scores = sorted(decision.scores.items(), key=lambda item: item[1], reverse=True)
            margin = (
                ranked_scores[0][1] - ranked_scores[1][1]
                if len(ranked_scores) > 1
                else 0.0
            )
            records.append(
                {
                    "case_id": case_id,
                    "message": case["message"],
                    "critical": bool(case.get("critical")),
                    "expected_domain": case["domain"],
                    "expected_relation": case["relation"],
                    "actual_domain": decision.domain.value,
                    "actual_relation": decision.relation.value,
                    "source": decision.source,
                    "scores": decision.scores,
                    "margin": round(margin, 6),
                    "latency_ms": round(latency_ms, 2),
                    "correct": correct,
                }
            )

    total = len(records)
    correct_count = sum(record["correct"] for record in records)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        confusion[record["expected_domain"]][record["actual_domain"]] += 1

    non_scheduling = [record for record in records if record["expected_domain"] != "scheduling"]
    false_scheduling = [
        record for record in non_scheduling if record["actual_domain"] == "scheduling"
    ]
    latencies = [record["latency_ms"] for record in records]
    critical_cases = {
        case_id: outcomes
        for case_id, outcomes in by_case.items()
        if any(record["case_id"] == case_id and record["critical"] for record in records)
    }

    return {
        "runs": total,
        "accuracy": round(correct_count / total, 4) if total else 1.0,
        "false_scheduling_rate": (
            round(len(false_scheduling) / len(non_scheduling), 4)
            if non_scheduling
            else 0.0
        ),
        "confusion_matrix": {
            expected: dict(counts) for expected, counts in sorted(confusion.items())
        },
        "source_counts": dict(Counter(record["source"] for record in records)),
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


async def evaluate_conversations(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: LlamaCppClient,
    embeddings: LlamaCppEmbeddingClient,
    critical_repetitions: int,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    by_case: dict[str, list[bool]] = defaultdict(list)

    for case in cases:
        if case.get("kind") != "conversation":
            continue
        repetitions = critical_repetitions if case.get("critical") else 1
        for repetition in range(repetitions):
            agent, sessions, calendar = build_eval_agent(settings, llm, embeddings)
            session_id = f"live-{case['id']}-{repetition}"
            started = time.perf_counter()
            error: str | None = None
            try:
                for user_message in case["turns"]:
                    _ = "".join(
                        [chunk async for chunk in agent.respond(session_id, user_message)]
                    )
            except Exception as exc:  # noqa: BLE001 - eval reports runtime failures
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
        httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as embedding_http,
    ):
        llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=llm_http,
        )
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=embedding_http,
        )

        router = build_router(embeddings)
        routing = await evaluate_routing(cases, router, args.critical_repetitions)
        conversations = await evaluate_conversations(
            cases,
            settings,
            llm,
            embeddings,
            args.critical_repetitions,
        )

    report = {
        "routing": routing,
        "conversations": conversations,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)

    passed = (
        routing["accuracy"] == 1.0
        and routing["false_scheduling_rate"] == 0.0
        and conversations["pass_rate"] == 1.0
        and conversations["unexpected_calendar_writes"] == 0
    )
    return 0 if passed or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
