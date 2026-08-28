from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.agent.router import SemanticRouter
from app.domain.conversation import ActiveWorkflow, ChatTurn, SessionState
from app.domain.routing import RoutingDecision
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient


@dataclass(frozen=True)
class RoutingCase:
    case_id: str
    category: str
    history: tuple[ChatTurn, ...]
    message: str
    active_workflow: str | None
    expected_domain: str
    expected_relation: str


@dataclass(frozen=True)
class DecisionResult:
    decision: RoutingDecision
    latency_ms: float
    margin: float


@dataclass(frozen=True)
class CaseResult:
    case: RoutingCase
    strategy: str
    decision: RoutingDecision
    latency_ms: float
    margin: float
    correct: bool


STRATEGIES = ("current-only", "previous+current", "adaptive")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare routing with current-only, previous+current and adaptive context."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("contextual_routing_cases.jsonl"),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_cases(path: Path) -> list[RoutingCase]:
    cases: list[RoutingCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        payload: dict[str, Any] = json.loads(raw)
        case_id = str(payload.get("id", "")).strip()
        if not case_id or case_id in seen:
            raise ValueError(f"Invalid or duplicate id at {path}:{line_number}: {case_id!r}")
        history_payload = payload.get("history")
        if not isinstance(history_payload, list):
            raise ValueError(f"Case {case_id} requires history")
        history = tuple(
            ChatTurn(role=str(turn["role"]), content=str(turn["content"]))
            for turn in history_payload
        )
        case = RoutingCase(
            case_id=case_id,
            category=str(payload["category"]),
            history=history,
            message=str(payload["message"]).strip(),
            active_workflow=payload.get("active_workflow"),
            expected_domain=str(payload["expected_domain"]),
            expected_relation=str(payload["expected_relation"]),
        )
        if not case.message:
            raise ValueError(f"Case {case_id} requires a message")
        seen.add(case_id)
        cases.append(case)
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases


def build_state(case: RoutingCase) -> SessionState:
    state = SessionState(session_id=f"contextual-routing-{case.case_id}")
    state.turns.extend(case.history)
    if case.active_workflow == ActiveWorkflow.SCHEDULING.value:
        state.active_workflow = ActiveWorkflow.SCHEDULING
    return state


def last_user_message(case: RoutingCase) -> str | None:
    for turn in reversed(case.history):
        if turn.role == "user" and turn.content.strip():
            return turn.content.strip()
    return None


def contextual_query(case: RoutingCase) -> str:
    previous = last_user_message(case)
    if previous is None:
        return case.message
    return f"Previous visitor message: {previous}\nCurrent visitor message: {case.message}"


def score_margin(decision: RoutingDecision) -> float:
    scores = sorted(decision.scores.values(), reverse=True)
    if len(scores) < 2:
        return 0.0
    return scores[0] - scores[1]


async def route_once(
    router: SemanticRouter,
    state: SessionState,
    query: str,
) -> DecisionResult:
    started = time.perf_counter()
    decision = await router.route(state, query)
    return DecisionResult(
        decision=decision,
        latency_ms=(time.perf_counter() - started) * 1000,
        margin=score_margin(decision),
    )


def is_correct(case: RoutingCase, decision: RoutingDecision) -> bool:
    return (
        decision.domain.value == case.expected_domain
        and decision.relation.value == case.expected_relation
    )


def choose_adaptive(
    current: DecisionResult,
    contextual: DecisionResult,
) -> DecisionResult:
    if contextual.margin <= current.margin:
        return DecisionResult(
            decision=current.decision,
            latency_ms=current.latency_ms + contextual.latency_ms,
            margin=current.margin,
        )
    return DecisionResult(
        decision=contextual.decision,
        latency_ms=current.latency_ms + contextual.latency_ms,
        margin=contextual.margin,
    )


async def evaluate(
    cases: list[RoutingCase],
    router: SemanticRouter,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        state = build_state(case)
        current = await route_once(router, state, case.message)
        contextual = await route_once(router, state, contextual_query(case))
        adaptive = choose_adaptive(current, contextual)

        for strategy, routed in (
            ("current-only", current),
            ("previous+current", contextual),
            ("adaptive", adaptive),
        ):
            results.append(
                CaseResult(
                    case=case,
                    strategy=strategy,
                    decision=routed.decision,
                    latency_ms=routed.latency_ms,
                    margin=routed.margin,
                    correct=is_correct(case, routed.decision),
                )
            )
    return results


def summarize(results: list[CaseResult], strategy: str) -> dict[str, Any]:
    selected = [result for result in results if result.strategy == strategy]
    correct = sum(result.correct for result in selected)
    non_scheduling = [
        result for result in selected if result.case.expected_domain != "scheduling"
    ]
    false_scheduling = sum(
        result.decision.domain.value == "scheduling" for result in non_scheduling
    )
    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for result in selected:
        by_category[result.case.category].append(result)
    latencies = [result.latency_ms for result in selected]
    margins = [result.margin for result in selected]
    return {
        "strategy": strategy,
        "total": len(selected),
        "correct": correct,
        "accuracy": correct / len(selected),
        "false_scheduling": false_scheduling,
        "non_scheduling": len(non_scheduling),
        "latency_p50": statistics.median(latencies),
        "margin_p50": statistics.median(margins),
        "by_category": {
            category: (sum(item.correct for item in items), len(items))
            for category, items in sorted(by_category.items())
        },
    }


def print_report(results: list[CaseResult], *, verbose: bool) -> None:
    summaries = {strategy: summarize(results, strategy) for strategy in STRATEGIES}
    total_cases = summaries["current-only"]["total"]
    categories = Counter(
        result.case.category
        for result in results
        if result.strategy == "current-only"
    )

    print("CONTEXTUAL ROUTING EVAL")
    print(f"Cases: {total_cases}")
    print("Categories: " + ", ".join(f"{name}={count}" for name, count in sorted(categories.items())))

    for strategy in STRATEGIES:
        summary = summaries[strategy]
        print(f"\n{strategy.upper()}")
        print(f"accuracy: {summary['correct']}/{summary['total']} ({summary['accuracy']:.1%})")
        print(
            "false scheduling: "
            f"{summary['false_scheduling']}/{summary['non_scheduling']}"
        )
        print(f"latency p50: {summary['latency_p50']:.2f} ms")
        print(f"margin p50: {summary['margin_p50']:.6f}")
        print(
            "categories: "
            + ", ".join(
                f"{category}={correct}/{total}"
                for category, (correct, total) in summary["by_category"].items()
            )
        )

    current = summaries["current-only"]
    print("\nCHANGES VS CURRENT-ONLY")
    for strategy in ("previous+current", "adaptive"):
        current_by_id = {
            result.case.case_id: result
            for result in results
            if result.strategy == "current-only"
        }
        candidate = [result for result in results if result.strategy == strategy]
        improvements = [
            result.case.case_id
            for result in candidate
            if result.correct and not current_by_id[result.case.case_id].correct
        ]
        regressions = [
            result.case.case_id
            for result in candidate
            if not result.correct and current_by_id[result.case.case_id].correct
        ]
        print(
            f"{strategy}: improvements={len(improvements)} "
            f"regressions={len(regressions)}"
        )
        if improvements:
            print("  improved: " + ", ".join(improvements))
        if regressions:
            print("  regressed: " + ", ".join(regressions))

    eligible = [
        summaries[strategy]
        for strategy in ("previous+current", "adaptive")
        if summaries[strategy]["correct"] > current["correct"]
        and summaries[strategy]["false_scheduling"] <= current["false_scheduling"]
    ]
    print("\nDECISION")
    if not eligible:
        print("KEEP CURRENT-ONLY")
        print("No contextual strategy strictly improves accuracy without increasing false scheduling.")
    else:
        winner = max(
            eligible,
            key=lambda item: (
                item["correct"],
                -item["false_scheduling"],
                -item["latency_p50"],
            ),
        )
        print(f"CANDIDATE: {winner['strategy']}")
        print("Evaluation result only; production router is unchanged.")

    if verbose:
        print("\nFAILURES")
        for strategy in STRATEGIES:
            failures = [
                result for result in results
                if result.strategy == strategy and not result.correct
            ]
            print(f"{strategy}: {len(failures)}")
            for result in failures:
                print(
                    f"- {result.case.case_id}: expected="
                    f"{result.case.expected_domain}/{result.case.expected_relation} "
                    f"actual={result.decision.domain.value}/{result.decision.relation.value} "
                    f"margin={result.margin:.6f}"
                )


async def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases)
    settings = Settings.from_env()
    async with httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as http:
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=http,
        )
        router = SemanticRouter(embeddings)
        await router.warm()
        results = await evaluate(cases, router)

    print_report(results, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
