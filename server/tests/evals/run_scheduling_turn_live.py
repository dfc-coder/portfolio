from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from app.agent.scheduler import Scheduler, SchedulingTurn
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


TRACKED_FIELDS = (
    "intent",
    "start_date",
    "end_date",
    "slot_id",
    "visitor_name",
    "visitor_email",
    "subject",
)


class RecordingLlm:
    """Transparent LLM proxy that records whether structured output validated."""

    def __init__(self, inner: LlamaCppClient) -> None:
        self._inner = inner
        self.last_raw: str | None = None
        self.last_schema_valid: bool | None = None
        self.last_error: str | None = None

    def reset(self) -> None:
        self.last_raw = None
        self.last_schema_valid = None
        self.last_error = None

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        self.reset()
        try:
            raw = await self._inner.complete(messages, config, response_schema=response_schema)
        except Exception as exc:
            self.last_schema_valid = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

        self.last_raw = raw
        if response_schema is None:
            self.last_schema_valid = True
            return raw

        try:
            response_schema.model_validate_json(raw)
            self.last_schema_valid = True
        except Exception as exc:  # noqa: BLE001 - eval records validation failures verbatim
            self.last_schema_valid = False
            self.last_error = f"{type(exc).__name__}: {exc}"
        return raw

    async def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        async for chunk in self._inner.stream(messages, config):
            yield chunk

    async def health(self) -> bool:
        return await self._inner.health()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate SchedulingTurn schema validity and semantic accuracy on the live SLM.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("scheduling_turn_cases.jsonl"),
    )
    parser.add_argument("--critical-repetitions", type=int, default=5)
    parser.add_argument("--min-schema-valid", type=float, default=0.99)
    parser.add_argument("--min-semantic-accuracy", type=float, default=0.95)
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
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not case.get("id") or not case.get("message") or not case.get("expected"):
            raise ValueError(f"Invalid scheduling eval case at {path}:{line_number}")
        cases.append(case)
    return cases


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def configure_state(
    case: dict[str, Any],
    repetition: int,
    policy: SchedulingPolicy,
) -> SessionState:
    state = SessionState(session_id=f"scheduling-eval-{case['id']}-{repetition}")
    raw_state = case.get("state") or {}
    if raw_state.get("active_workflow") != "scheduling":
        return state

    state.active_workflow = ActiveWorkflow.SCHEDULING
    stage = raw_state.get("stage")
    start = datetime.now(timezone.utc).astimezone(policy.timezone) + timedelta(days=7)
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

    return state


def normalize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    return value


def resolve_expected(value: Any, policy: SchedulingPolicy) -> Any:
    if isinstance(value, dict) and "$date_offset_days" in value:
        local_today = datetime.now(timezone.utc).astimezone(policy.timezone).date()
        return (local_today + timedelta(days=int(value["$date_offset_days"]))).isoformat()
    return normalize_value(value)


def strings_match(field: str, expected: str, actual: str) -> bool:
    expected_normalized = " ".join(expected.split()).casefold()
    actual_normalized = " ".join(actual.split()).casefold()
    if field == "subject":
        return (
            expected_normalized == actual_normalized
            or expected_normalized in actual_normalized
            or actual_normalized in expected_normalized
        )
    return expected_normalized == actual_normalized


def values_match(field: str, expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return strings_match(field, expected, actual)
    return expected == actual


def score_turn(
    case: dict[str, Any],
    turn: SchedulingTurn,
    policy: SchedulingPolicy,
    schema_valid: bool,
) -> tuple[bool, dict[str, bool], list[str]]:
    field_results: dict[str, bool] = {}
    failures: list[str] = []

    for field, expected_raw in case["expected"].items():
        if field not in TRACKED_FIELDS:
            raise ValueError(f"Unknown expected field {field!r} in case {case['id']}")
        expected = resolve_expected(expected_raw, policy)
        actual = normalize_value(getattr(turn, field))
        correct = values_match(field, expected, actual)
        field_results[field] = correct
        if not correct:
            failures.append(f"{field}: expected={expected!r} actual={actual!r}")

    for field in case.get("must_be_null", []):
        if field not in TRACKED_FIELDS:
            raise ValueError(f"Unknown null field {field!r} in case {case['id']}")
        actual = normalize_value(getattr(turn, field))
        correct = actual is None
        field_results[f"null:{field}"] = correct
        if not correct:
            failures.append(f"{field}: expected=None actual={actual!r}")

    if not schema_valid:
        failures.append("schema_invalid")

    return schema_valid and all(field_results.values()), field_results, failures


def build_scheduler(
    settings: Settings,
    llm: RecordingLlm,
) -> tuple[Scheduler, SchedulingPolicy]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    calendar = InMemoryCalendarGateway()
    slots = SlotService(calendar, policy)
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
    return scheduler, policy


async def evaluate(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: RecordingLlm,
    critical_repetitions: int,
) -> dict[str, Any]:
    scheduler, policy = build_scheduler(settings, llm)
    records: list[dict[str, Any]] = []
    critical_outcomes: dict[str, list[bool]] = defaultdict(list)
    field_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    null_assertions = 0
    hallucinated_fields = 0

    for case in cases:
        repetitions = critical_repetitions if case.get("critical") else 1
        for repetition in range(repetitions):
            state = configure_state(case, repetition, policy)
            relation = RouteRelation(case.get("relation", "new"))
            llm.reset()
            started = time.perf_counter()
            turn = await scheduler._interpret(state, case["message"], relation)  # noqa: SLF001
            latency_ms = (time.perf_counter() - started) * 1000
            schema_valid = llm.last_schema_valid is True
            semantic_success, field_results, semantic_failures = score_turn(
                case,
                turn,
                policy,
                schema_valid,
            )

            for field, correct in field_results.items():
                field_stats[field]["total"] += 1
                field_stats[field]["correct"] += int(correct)
                if field.startswith("null:"):
                    null_assertions += 1
                    hallucinated_fields += int(not correct)

            if case.get("critical"):
                critical_outcomes[case["id"]].append(semantic_success)

            records.append(
                {
                    "case_id": case["id"],
                    "message": case["message"],
                    "critical": bool(case.get("critical")),
                    "relation": relation.value,
                    "schema_valid": schema_valid,
                    "expected": case["expected"],
                    "actual": turn.model_dump(mode="json"),
                    "semantic_success": semantic_success,
                    "semantic_failures": semantic_failures,
                    "latency_ms": round(latency_ms, 2),
                    "llm_error": llm.last_error,
                    "raw": llm.last_raw if not semantic_success else None,
                }
            )

    total = len(records)
    schema_valid_count = sum(record["schema_valid"] for record in records)
    semantic_success_count = sum(record["semantic_success"] for record in records)
    latencies = [record["latency_ms"] for record in records]

    field_accuracy = {
        field: round(stats["correct"] / stats["total"], 4)
        for field, stats in sorted(field_stats.items())
        if stats["total"]
    }
    critical_passed = sum(all(outcomes) for outcomes in critical_outcomes.values())

    return {
        "runs": total,
        "schema_valid_rate": round(schema_valid_count / total, 4) if total else 0.0,
        "semantic_accuracy": round(semantic_success_count / total, 4) if total else 0.0,
        "intent_accuracy": field_accuracy.get("intent", 0.0),
        "field_accuracy": field_accuracy,
        "hallucinated_field_rate": (
            round(hallucinated_fields / null_assertions, 4) if null_assertions else 0.0
        ),
        "critical_pass_k": {
            "passed": critical_passed,
            "total": len(critical_outcomes),
            "k": critical_repetitions,
        },
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "failures": [record for record in records if not record["semantic_success"]],
    }


def verdict(
    results: dict[str, Any],
    min_schema_valid: float,
    min_semantic_accuracy: float,
) -> dict[str, str]:
    critical = results["critical_pass_k"]
    all_critical_pass = critical["passed"] == critical["total"]

    if (
        results["schema_valid_rate"] >= min_schema_valid
        and results["semantic_accuracy"] >= min_semantic_accuracy
        and all_critical_pass
    ):
        return {
            "status": "structured_decoding_sufficient",
            "next_step": "Keep Qwen3.5-0.8B and the current SchedulingTurn architecture.",
        }
    if results["schema_valid_rate"] < min_schema_valid:
        return {
            "status": "structured_output_unreliable",
            "next_step": "Inspect llama.cpp JSON-schema enforcement/fallback before changing model size.",
        }
    return {
        "status": "semantic_accuracy_insufficient",
        "next_step": "Run the same corpus against Qwen3.5-2B before considering fine-tuning.",
    }


async def main() -> int:
    args = parse_args()
    if args.critical_repetitions < 1:
        raise ValueError("--critical-repetitions must be >= 1")
    if not 0.0 <= args.min_schema_valid <= 1.0:
        raise ValueError("--min-schema-valid must be between 0 and 1")
    if not 0.0 <= args.min_semantic_accuracy <= 1.0:
        raise ValueError("--min-semantic-accuracy must be between 0 and 1")

    settings = Settings.from_env()
    cases = load_cases(args.cases)

    async with httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as http:
        base_llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=http,
        )
        llm = RecordingLlm(base_llm)
        if not await llm.health():
            report = {
                "health": {"llm": False},
                "error": "The live model service is not ready.",
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2

        results = await evaluate(
            cases,
            settings,
            llm,
            args.critical_repetitions,
        )

    decision = verdict(
        results,
        args.min_schema_valid,
        args.min_semantic_accuracy,
    )
    report = {
        "health": {"llm": True},
        "model": settings.llama_model,
        "dataset": {
            "cases": len(cases),
            "critical_cases": sum(bool(case.get("critical")) for case in cases),
            "critical_repetitions": args.critical_repetitions,
        },
        "thresholds": {
            "schema_valid_rate": args.min_schema_valid,
            "semantic_accuracy": args.min_semantic_accuracy,
            "critical_cases": "all repetitions must pass",
        },
        "results": results,
        "decision": decision,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    failed = decision["status"] != "structured_decoding_sufficient"
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
