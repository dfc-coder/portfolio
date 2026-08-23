from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from app.agent.router import SemanticRouter, _ACTIVE_SCHEDULING_ROUTES, _NEW_ROUTES
from app.agent.scheduler import Scheduler, SchedulingIntent, SchedulingTurn
from app.domain.conversation import ActiveWorkflow, SessionState
from app.domain.routing import RouteRelation
from app.domain.scheduling import OfferedSlot, PendingBooking
from app.infrastructure.calendar.memory import InMemoryCalendarGateway
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.ports.llm import GenerationConfig
from app.ports.reranker import RerankerPort
from app.scheduling.policy import SchedulingPolicy
from app.scheduling.slots import SlotService


ROOT = Path(__file__).resolve().parent
SCHEDULING_CASES = ROOT / "scheduling_turn_cases.jsonl"
ROUTING_CASES = ROOT / "cases.jsonl"
TRACKED_FIELDS = (
    "intent",
    "start_date",
    "end_date",
    "slot_id",
    "visitor_name",
    "visitor_email",
    "subject",
)


@dataclass(frozen=True)
class InferenceProfile:
    name: str
    prompt_mode: str
    thinking: bool
    temperature: float
    top_p: float
    top_k: int
    min_p: float | None
    presence_penalty: float | None
    repeat_penalty: float | None


# Unsloth Qwen3.5 recommended profiles plus the project's current planner settings.
PROFILES = (
    InferenceProfile("project_current", "production", False, 0.15, 0.90, 20, None, None, None),
    InferenceProfile("unsloth_instruct_general", "production", False, 0.70, 0.80, 20, 0.0, 1.5, 1.0),
    InferenceProfile("unsloth_instruct_reasoning", "production", False, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("unsloth_thinking_general", "production", True, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("unsloth_thinking_precise", "production", True, 0.60, 0.95, 20, 0.0, 0.0, 1.0),
    InferenceProfile("minimal_instruct_general", "minimal", False, 0.70, 0.80, 20, 0.0, 1.5, 1.0),
    InferenceProfile("minimal_instruct_reasoning", "minimal", False, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("minimal_thinking_general", "minimal", True, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
)


class EmptyReranker(RerankerPort):
    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        return [0.0] * len(documents)

    async def health(self) -> bool:
        return True


class ProfileLlm:
    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        model: str,
        profile: InferenceProfile,
        max_tokens: int,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._profile = profile
        self._max_tokens = max_tokens
        self.last_raw: str | None = None
        self.last_schema_valid: bool | None = None
        self.last_error: str | None = None

    def reset(self) -> None:
        self.last_raw = None
        self.last_schema_valid = None
        self.last_error = None

    async def health(self) -> bool:
        try:
            response = await self._http.get(f"{self._base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        self.reset()
        p = self._profile
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "temperature": p.temperature,
            "top_p": p.top_p,
            "top_k": p.top_k,
            "max_tokens": self._max_tokens,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": p.thinking},
        }
        if p.min_p is not None:
            payload["min_p"] = p.min_p
        if p.presence_penalty is not None:
            payload["presence_penalty"] = p.presence_penalty
        if p.repeat_penalty is not None:
            payload["repeat_penalty"] = p.repeat_penalty
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            }

        try:
            response = await self._http.post(f"{self._base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            raw = message.get("content") or ""
            self.last_raw = raw
            if response_schema is None:
                self.last_schema_valid = True
                return raw
            response_schema.model_validate_json(raw)
            self.last_schema_valid = True
            return raw
        except Exception as exc:  # noqa: BLE001 - diagnostic records transport/schema failures
            self.last_schema_valid = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    async def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("stream is not used by the model diagnostic")
        yield ""  # pragma: no cover


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Qwen3.5 inference configuration and model capacity on agent-critical tasks.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="benchmark-model")
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--critical-repetitions", type=int, default=3)
    parser.add_argument("--finalists", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--profiles", nargs="*", choices=[p.name for p in PROFILES])
    return parser.parse_args()


def load_jsonl(path: Path, kind: str | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        case = json.loads(raw)
        if kind is None or case.get("kind") == kind:
            cases.append(case)
    return cases


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    return value


def resolve_expected(value: Any, policy: SchedulingPolicy) -> Any:
    if isinstance(value, dict) and "$date_offset_days" in value:
        today = datetime.now(timezone.utc).astimezone(policy.timezone).date()
        return (today + timedelta(days=int(value["$date_offset_days"]))).isoformat()
    return normalize(value)


def strings_match(field: str, expected: str, actual: str) -> bool:
    expected_norm = " ".join(expected.split()).casefold()
    actual_norm = " ".join(actual.split()).casefold()
    if field == "subject":
        return expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm
    return expected_norm == actual_norm


def values_match(field: str, expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return strings_match(field, expected, actual)
    return expected == actual


def configure_state(case: dict[str, Any], repetition: int, policy: SchedulingPolicy) -> SessionState:
    state = SessionState(session_id=f"diag-{case.get('id', 'case')}-{repetition}")
    raw_state = case.get("state") or {}
    if raw_state.get("active_workflow") != "scheduling":
        return state

    state.active_workflow = ActiveWorkflow.SCHEDULING
    stage = raw_state.get("stage")
    start = datetime.now(timezone.utc).astimezone(policy.timezone) + timedelta(days=7)
    first = OfferedSlot(start=start, end=start + timedelta(minutes=30))
    second = OfferedSlot(start=start + timedelta(minutes=45), end=start + timedelta(minutes=75))
    if stage in {"scheduling_slot", "scheduling_details", "scheduling_confirmation"}:
        state.scheduling.offered_slots = {"S1": first, "S2": second}
    if stage in {"scheduling_details", "scheduling_confirmation"}:
        state.scheduling.selected_slot_id = "S1"
    if stage == "scheduling_confirmation":
        state.scheduling.visitor_name = "Ana"
        state.scheduling.visitor_email = "ana@example.com"
        state.scheduling.subject = "Architecture discussion"
        state.scheduling.pending_booking = PendingBooking(
            booking_id="diag-booking",
            slot=first,
            visitor_name="Ana",
            visitor_email="ana@example.com",
            subject="Architecture discussion",
        )
    return state


def scheduling_score(
    case: dict[str, Any],
    turn: SchedulingTurn,
    policy: SchedulingPolicy,
    schema_valid: bool,
) -> tuple[bool, int, int, int, int, list[str]]:
    failures: list[str] = []
    correct_fields = 0
    total_fields = 0
    hallucinated = 0
    null_assertions = 0

    for field, expected_raw in case["expected"].items():
        if field not in TRACKED_FIELDS:
            continue
        expected = resolve_expected(expected_raw, policy)
        actual = normalize(getattr(turn, field))
        ok = values_match(field, expected, actual)
        total_fields += 1
        correct_fields += int(ok)
        if not ok:
            failures.append(f"{field}: expected={expected!r} actual={actual!r}")

    for field in case.get("must_be_null", []):
        actual = normalize(getattr(turn, field))
        ok = actual is None
        total_fields += 1
        null_assertions += 1
        correct_fields += int(ok)
        hallucinated += int(not ok)
        if not ok:
            failures.append(f"{field}: expected=None actual={actual!r}")

    if not schema_valid:
        failures.append("schema_invalid")
    return schema_valid and not failures, correct_fields, total_fields, hallucinated, null_assertions, failures


def build_scheduler(settings: Settings, llm: ProfileLlm) -> tuple[Scheduler, SchedulingPolicy]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    calendar = InMemoryCalendarGateway()
    scheduler = Scheduler(
        llm,
        SlotService(calendar, policy),
        calendar,
        policy,
        GenerationConfig(temperature=0.15, max_tokens=96, top_p=0.9, top_k=20),
    )
    return scheduler, policy


def minimal_scheduling_messages(
    state: SessionState,
    user_message: str,
    relation: RouteRelation,
    policy: SchedulingPolicy,
) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc).astimezone(policy.timezone)
    context: dict[str, Any] = {
        "current_time": now.isoformat(),
        "timezone": policy.config.timezone,
        "relation": relation.value,
        "visitor_message": user_message,
    }
    if state.scheduling.offered_slots:
        context["offered_slot_ids"] = list(state.scheduling.offered_slots)
    return [
        {
            "role": "system",
            "content": (
                "Extract ONLY information explicitly stated in visitor_message into SchedulingTurn. "
                "Do not copy values from context into output. Context exists only to resolve references. "
                "request=asks to arrange/check a meeting; inform=provides date or meeting details; "
                "select=chooses an offered slot; confirm=explicitly confirms; cancel=cancels; "
                "other=not scheduling. Resolve relative dates using current_time. "
                "Omit every field not explicitly present in visitor_message."
            ),
        },
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


async def evaluate_scheduling(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: ProfileLlm,
    profile: InferenceProfile,
    repetitions: int,
    critical_only: bool,
) -> dict[str, Any]:
    scheduler, policy = build_scheduler(settings, llm)
    records: list[dict[str, Any]] = []
    correct_fields = total_fields = hallucinated = null_assertions = 0
    schema_valid = semantic_success = intent_correct = intent_total = 0
    latencies: list[float] = []
    critical_outcomes: dict[str, list[bool]] = defaultdict(list)

    selected = [case for case in cases if case.get("critical")] if critical_only else cases
    total_runs = sum(repetitions if case.get("critical") else 1 for case in selected)
    index = 0
    for case in selected:
        runs = repetitions if case.get("critical") else 1
        for repetition in range(runs):
            index += 1
            state = configure_state(case, repetition, policy)
            relation = RouteRelation(case.get("relation", "new"))
            started = time.perf_counter()
            try:
                if profile.prompt_mode == "production":
                    turn = await scheduler._interpret(state, case["message"], relation)  # noqa: SLF001
                else:
                    raw = await llm.complete(
                        minimal_scheduling_messages(state, case["message"], relation, policy),
                        GenerationConfig(temperature=profile.temperature, max_tokens=256),
                        response_schema=SchedulingTurn,
                    )
                    turn = SchedulingTurn.model_validate_json(raw)
            except Exception:  # noqa: BLE001 - error is captured by llm and scored as failure
                turn = SchedulingTurn(intent=SchedulingIntent.OTHER)
            latency = (time.perf_counter() - started) * 1000
            latencies.append(latency)
            valid = llm.last_schema_valid is True
            ok, cf, tf, hf, na, failures = scheduling_score(case, turn, policy, valid)
            correct_fields += cf
            total_fields += tf
            hallucinated += hf
            null_assertions += na
            schema_valid += int(valid)
            semantic_success += int(ok)
            if "intent" in case["expected"]:
                intent_total += 1
                intent_correct += int(turn.intent.value == case["expected"]["intent"])
            if case.get("critical"):
                critical_outcomes[case["id"]].append(ok)
            if not ok:
                records.append({
                    "case_id": case["id"],
                    "message": case["message"],
                    "failures": failures,
                    "actual": turn.model_dump(mode="json"),
                    "raw": llm.last_raw,
                    "error": llm.last_error,
                })
            print(f"  scheduling {index:>3}/{total_runs} {case['id']} {'PASS' if ok else 'FAIL'} {latency:.0f}ms", flush=True)

    runs = max(1, index)
    return {
        "runs": index,
        "schema_valid_rate": round(schema_valid / runs, 4),
        "semantic_accuracy": round(semantic_success / runs, 4),
        "intent_accuracy": round(intent_correct / intent_total, 4) if intent_total else 0.0,
        "field_accuracy": round(correct_fields / total_fields, 4) if total_fields else 0.0,
        "hallucinated_field_rate": round(hallucinated / null_assertions, 4) if null_assertions else 0.0,
        "critical_pass_rate": (
            round(sum(all(v) for v in critical_outcomes.values()) / len(critical_outcomes), 4)
            if critical_outcomes else 1.0
        ),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "failures": records,
    }


async def evaluate_routing(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: ProfileLlm,
    repetitions: int,
    critical_only: bool,
) -> dict[str, Any]:
    router = SemanticRouter(
        EmptyReranker(),
        llm,
        GenerationConfig(temperature=0.05, max_tokens=48, top_p=0.8, top_k=10),
        min_score=1.0,
        min_margin=1.0,
    )
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    selected = [case for case in cases if case.get("critical")] if critical_only else cases
    records: list[dict[str, Any]] = []
    correct = false_scheduling = non_scheduling = schema_valid = 0
    latencies: list[float] = []
    critical_outcomes: dict[str, list[bool]] = defaultdict(list)
    total_runs = sum(repetitions if case.get("critical") else 1 for case in selected)
    index = 0

    for case in selected:
        runs = repetitions if case.get("critical") else 1
        for repetition in range(runs):
            index += 1
            state = configure_state(case, repetition, policy)
            routes = _ACTIVE_SCHEDULING_ROUTES if state.active_workflow == ActiveWorkflow.SCHEDULING else _NEW_ROUTES
            query = router._query(state, case["message"])  # noqa: SLF001
            started = time.perf_counter()
            decision = await router._judge(query, routes, [])  # noqa: SLF001
            latency = (time.perf_counter() - started) * 1000
            latencies.append(latency)
            ok = decision.domain.value == case["domain"] and decision.relation.value == case["relation"]
            correct += int(ok)
            schema_valid += int(llm.last_schema_valid is True)
            if case["domain"] != "scheduling":
                non_scheduling += 1
                false_scheduling += int(decision.domain.value == "scheduling")
            if case.get("critical"):
                critical_outcomes[case["id"]].append(ok)
            if not ok:
                records.append({
                    "case_id": case["id"],
                    "message": case["message"],
                    "expected": f"{case['domain']}/{case['relation']}",
                    "actual": f"{decision.domain.value}/{decision.relation.value}",
                    "raw": llm.last_raw,
                    "error": llm.last_error,
                })
            print(f"  routing    {index:>3}/{total_runs} {case['id']} {'PASS' if ok else 'FAIL'} {latency:.0f}ms", flush=True)

    runs = max(1, index)
    return {
        "runs": index,
        "schema_valid_rate": round(schema_valid / runs, 4),
        "accuracy": round(correct / runs, 4),
        "false_scheduling_rate": round(false_scheduling / non_scheduling, 4) if non_scheduling else 0.0,
        "critical_pass_rate": (
            round(sum(all(v) for v in critical_outcomes.values()) / len(critical_outcomes), 4)
            if critical_outcomes else 1.0
        ),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "failures": records,
    }


def profile_score(result: dict[str, Any]) -> float:
    s = result["scheduling"]
    r = result["routing"]
    return (
        0.40 * s["semantic_accuracy"]
        + 0.25 * r["accuracy"]
        + 0.10 * s["intent_accuracy"]
        + 0.10 * s["schema_valid_rate"]
        + 0.10 * r["schema_valid_rate"]
        + 0.05 * (1.0 - s["hallucinated_field_rate"])
        - 0.15 * r["false_scheduling_rate"]
    )


def is_sufficient(result: dict[str, Any]) -> bool:
    s = result["scheduling"]
    r = result["routing"]
    return (
        s["schema_valid_rate"] >= 0.99
        and s["semantic_accuracy"] >= 0.95
        and s["intent_accuracy"] >= 0.95
        and s["hallucinated_field_rate"] <= 0.02
        and s["critical_pass_rate"] == 1.0
        and r["schema_valid_rate"] >= 0.99
        and r["accuracy"] >= 0.95
        and r["false_scheduling_rate"] == 0.0
        and r["critical_pass_rate"] == 1.0
    )


async def run_profile(
    profile: InferenceProfile,
    scheduling_cases: list[dict[str, Any]],
    routing_cases: list[dict[str, Any]],
    settings: Settings,
    http: httpx.AsyncClient,
    args: argparse.Namespace,
    repetitions: int,
    critical_only: bool,
) -> dict[str, Any]:
    print(
        f"\n== {profile.name} prompt={profile.prompt_mode} thinking={profile.thinking} "
        f"temp={profile.temperature} top_p={profile.top_p} ==",
        flush=True,
    )
    llm = ProfileLlm(http, args.base_url, args.model, profile, args.max_tokens)
    scheduling = await evaluate_scheduling(
        scheduling_cases, settings, llm, profile, repetitions, critical_only,
    )
    routing = await evaluate_routing(routing_cases, settings, llm, repetitions, critical_only)
    result = {
        "profile": profile.__dict__,
        "scheduling": scheduling,
        "routing": routing,
    }
    result["score"] = round(profile_score(result), 4)
    result["sufficient"] = is_sufficient(result) if not critical_only else False
    return result


async def main() -> int:
    args = parse_args()
    if args.critical_repetitions < 1 or args.finalists < 1:
        raise ValueError("critical repetitions and finalists must be >= 1")

    settings = Settings.from_env()
    scheduling_cases = load_jsonl(SCHEDULING_CASES)
    routing_cases = load_jsonl(ROUTING_CASES, "routing")
    profiles = [p for p in PROFILES if not args.profiles or p.name in args.profiles]

    timeout = max(settings.llama_timeout_seconds, 120.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        probe = ProfileLlm(http, args.base_url, args.model, profiles[0], args.max_tokens)
        if not await probe.health():
            raise RuntimeError(f"Model server is not healthy at {args.base_url}")

        # Phase 1: every configuration on critical cases only.
        screening: list[dict[str, Any]] = []
        for profile in profiles:
            result = await run_profile(
                profile, scheduling_cases, routing_cases, settings, http, args, 1, True,
            )
            screening.append(result)

        finalists = sorted(screening, key=lambda item: item["score"], reverse=True)[: args.finalists]
        finalist_names = [item["profile"]["name"] for item in finalists]
        print(f"\nFinalists: {', '.join(finalist_names)}", flush=True)

        # Phase 2: finalists on the full corpus; critical cases repeated for consistency.
        final_results: list[dict[str, Any]] = []
        for name in finalist_names:
            profile = next(p for p in profiles if p.name == name)
            result = await run_profile(
                profile,
                scheduling_cases,
                routing_cases,
                settings,
                http,
                args,
                args.critical_repetitions,
                False,
            )
            final_results.append(result)

    final_results.sort(key=lambda item: item["score"], reverse=True)
    best = final_results[0]
    current = next((item for item in final_results if item["profile"]["name"] == "project_current"), None)
    if best["sufficient"]:
        status = "same_model_sufficient"
        next_step = f"Keep this model and use profile {best['profile']['name']}."
    else:
        status = "same_model_insufficient"
        next_step = "Benchmark the same diagnostic against Qwen3.5-2B; if needed, 4B."

    report = {
        "model_label": args.model_label,
        "model_api_name": args.model,
        "source": {
            "scheduling_cases": str(SCHEDULING_CASES),
            "routing_cases": str(ROUTING_CASES),
        },
        "thresholds": {
            "schema_valid_rate": 0.99,
            "scheduling_semantic_accuracy": 0.95,
            "intent_accuracy": 0.95,
            "hallucinated_field_rate_max": 0.02,
            "routing_accuracy": 0.95,
            "false_scheduling_rate": 0.0,
            "critical_pass_rate": 1.0,
        },
        "screening": [
            {
                "profile": item["profile"],
                "score": item["score"],
                "scheduling": {k: v for k, v in item["scheduling"].items() if k != "failures"},
                "routing": {k: v for k, v in item["routing"].items() if k != "failures"},
            }
            for item in sorted(screening, key=lambda result: result["score"], reverse=True)
        ],
        "finalists": final_results,
        "best_profile": best["profile"],
        "best_sufficient": best["sufficient"],
        "current_profile_tested_in_final": current is not None,
        "decision": {"status": status, "next_step": next_step},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== MODEL DIAGNOSTIC RESULT ===")
    print(json.dumps({
        "model_label": args.model_label,
        "best_profile": best["profile"]["name"],
        "best_score": best["score"],
        "sufficient": best["sufficient"],
        "scheduling": {k: v for k, v in best["scheduling"].items() if k != "failures"},
        "routing": {k: v for k, v in best["routing"].items() if k != "failures"},
        "decision": report["decision"],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
