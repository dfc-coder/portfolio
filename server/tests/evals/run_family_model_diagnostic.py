from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from app.agent.responder import Responder
from app.agent.scheduler import Scheduler
from app.domain.conversation import ChatTurn, SessionState
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.ports.llm import GenerationConfig
from app.scheduling.policy import SchedulingPolicy
from tests.evals.run_model_diagnostic import (
    InferenceProfile,
    evaluate_routing,
    evaluate_scheduling,
    load_jsonl,
)

ROOT = Path(__file__).resolve().parent
SCHEDULING_CASES = ROOT / "scheduling_turn_cases.jsonl"
ROUTING_CASES = ROOT / "cases.jsonl"
BUSINESS_CASES = ROOT / "business_response_cases.jsonl"

QWEN35_PROFILES = (
    InferenceProfile("qwen_project_current", "production", False, 0.15, 0.90, 20, None, None, None),
    InferenceProfile("qwen_unsloth_instruct_general", "production", False, 0.70, 0.80, 20, 0.0, 1.5, 1.0),
    InferenceProfile("qwen_unsloth_instruct_reasoning", "production", False, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("qwen_unsloth_thinking_general", "production", True, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("qwen_unsloth_thinking_precise", "production", True, 0.60, 0.95, 20, 0.0, 0.0, 1.0),
    InferenceProfile("qwen_minimal_instruct_general", "minimal", False, 0.70, 0.80, 20, 0.0, 1.5, 1.0),
    InferenceProfile("qwen_minimal_instruct_reasoning", "minimal", False, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
    InferenceProfile("qwen_minimal_thinking_general", "minimal", True, 1.00, 0.95, 20, 0.0, 1.5, 1.0),
)

# Gemma 4 does not use Qwen's enable_thinking chat-template flag. Test both the
# production prompt and the same minimal extraction prompt with conservative and
# balanced sampling so family comparison is not tied to Qwen-specific settings.
GEMMA4_PROFILES = (
    InferenceProfile("gemma_production_precise", "production", False, 0.20, 0.90, 20, None, None, 1.0),
    InferenceProfile("gemma_production_balanced", "production", False, 0.70, 0.90, 20, None, None, 1.0),
    InferenceProfile("gemma_minimal_precise", "minimal", False, 0.20, 0.90, 20, None, None, 1.0),
    InferenceProfile("gemma_minimal_balanced", "minimal", False, 0.70, 0.90, 20, None, None, 1.0),
)


class FamilyLlm:
    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        model: str,
        profile: InferenceProfile,
        max_tokens: int,
        family: str,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._profile = profile
        self._max_tokens = max_tokens
        self._family = family
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
        }
        if self._family == "qwen35":
            payload["chat_template_kwargs"] = {"enable_thinking": p.thinking}
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
            raw = response.json()["choices"][0]["message"].get("content") or ""
            self.last_raw = raw
            if response_schema is None:
                self.last_schema_valid = True
                return raw
            response_schema.model_validate_json(raw)
            self.last_schema_valid = True
            return raw
        except Exception as exc:  # noqa: BLE001 - benchmark must capture model/runtime failures
            self.last_schema_valid = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    async def stream(
        self,
        messages: list[dict[str, Any]],
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("stream is not used by the family diagnostic")
        yield ""  # pragma: no cover


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-family benchmark for the portfolio business representative.")
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="benchmark-model")
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--family", choices=("qwen35", "gemma4"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--critical-repetitions", type=int, default=5)
    parser.add_argument("--finalists", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser.parse_args()


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def business_case_ok(case: dict[str, Any], text: str) -> tuple[bool, list[str]]:
    normalized = " ".join(text.casefold().split())
    failures: list[str] = []
    for group in case.get("required_groups", []):
        if not any(token.casefold() in normalized for token in group):
            failures.append(f"missing one of {group!r}")
    for token in case.get("forbidden", []):
        if token.casefold() in normalized:
            failures.append(f"forbidden {token!r}")
    return not failures, failures


async def evaluate_business(
    cases: list[dict[str, Any]],
    settings: Settings,
    llm: FamilyLlm,
    repetitions: int,
    critical_only: bool,
) -> dict[str, Any]:
    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    responder = Responder(
        llm,
        profile,
        policy,
        GenerationConfig(temperature=0.2, max_tokens=180, top_p=0.9, top_k=20),
        Scheduler.PUBLIC_CAPABILITIES,
    )
    selected = [case for case in cases if case.get("critical")] if critical_only else cases
    total_runs = sum(repetitions if case.get("critical") else 1 for case in selected)
    index = correct = 0
    latencies: list[float] = []
    failures: list[dict[str, Any]] = []
    critical_outcomes: dict[str, list[bool]] = defaultdict(list)

    for case in selected:
        runs = repetitions if case.get("critical") else 1
        for repetition in range(runs):
            index += 1
            state = SessionState(session_id=f"business-{case['id']}-{repetition}")
            state.turns.append(ChatTurn(role="user", content=case["message"]))
            started = time.perf_counter()
            try:
                text = await llm.complete(
                    responder._messages(state),  # noqa: SLF001 - diagnostic evaluates production prompt
                    GenerationConfig(temperature=0.2, max_tokens=180),
                )
                ok, reasons = business_case_ok(case, text)
            except Exception:  # noqa: BLE001
                text = ""
                ok = False
                reasons = [llm.last_error or "generation_failed"]
            latency = (time.perf_counter() - started) * 1000
            latencies.append(latency)
            correct += int(ok)
            if case.get("critical"):
                critical_outcomes[case["id"]].append(ok)
            if not ok:
                failures.append({
                    "case_id": case["id"],
                    "message": case["message"],
                    "failures": reasons,
                    "actual": text,
                    "error": llm.last_error,
                })
            print(f"  business   {index:>3}/{total_runs} {case['id']} {'PASS' if ok else 'FAIL'} {latency:.0f}ms", flush=True)

    runs = max(1, index)
    return {
        "runs": index,
        "accuracy": round(correct / runs, 4),
        "critical_pass_rate": (
            round(sum(all(v) for v in critical_outcomes.values()) / len(critical_outcomes), 4)
            if critical_outcomes else 1.0
        ),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
        },
        "failures": failures,
    }


def score_result(result: dict[str, Any]) -> float:
    s = result["scheduling"]
    r = result["routing"]
    b = result["business"]
    return round(
        0.30 * s["semantic_accuracy"]
        + 0.20 * r["accuracy"]
        + 0.20 * b["accuracy"]
        + 0.08 * s["intent_accuracy"]
        + 0.06 * s["schema_valid_rate"]
        + 0.06 * r["schema_valid_rate"]
        + 0.05 * (1.0 - s["hallucinated_field_rate"])
        + 0.05 * min(s["critical_pass_rate"], r["critical_pass_rate"], b["critical_pass_rate"])
        - 0.15 * r["false_scheduling_rate"],
        4,
    )


def sufficient(result: dict[str, Any]) -> bool:
    s = result["scheduling"]
    r = result["routing"]
    b = result["business"]
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
        and b["accuracy"] >= 0.90
        and b["critical_pass_rate"] == 1.0
    )


async def run_profile(
    profile: InferenceProfile,
    scheduling_cases: list[dict[str, Any]],
    routing_cases: list[dict[str, Any]],
    business_cases: list[dict[str, Any]],
    settings: Settings,
    http: httpx.AsyncClient,
    args: argparse.Namespace,
    repetitions: int,
    critical_only: bool,
) -> dict[str, Any]:
    print(
        f"\n== {args.family}/{profile.name} prompt={profile.prompt_mode} "
        f"temp={profile.temperature} top_p={profile.top_p} ==",
        flush=True,
    )
    llm = FamilyLlm(http, args.base_url, args.model, profile, args.max_tokens, args.family)
    scheduling = await evaluate_scheduling(scheduling_cases, settings, llm, profile, repetitions, critical_only)
    routing = await evaluate_routing(routing_cases, settings, llm, repetitions, critical_only)
    business = await evaluate_business(business_cases, settings, llm, repetitions, critical_only)
    result = {
        "profile": asdict(profile),
        "scheduling": scheduling,
        "routing": routing,
        "business": business,
    }
    result["score"] = score_result(result)
    result["sufficient"] = sufficient(result) if not critical_only else False
    return result


async def main() -> int:
    args = parse_args()
    if args.critical_repetitions < 1 or args.finalists < 1:
        raise ValueError("critical repetitions and finalists must be >= 1")

    settings = Settings.from_env()
    scheduling_cases = load_jsonl(SCHEDULING_CASES)
    routing_cases = load_jsonl(ROUTING_CASES, "routing")
    business_cases = load_jsonl(BUSINESS_CASES)
    profiles = QWEN35_PROFILES if args.family == "qwen35" else GEMMA4_PROFILES

    timeout = max(settings.llama_timeout_seconds, 120.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        probe = FamilyLlm(http, args.base_url, args.model, profiles[0], args.max_tokens, args.family)
        if not await probe.health():
            raise RuntimeError(f"Model server is not healthy at {args.base_url}")

        screening: list[dict[str, Any]] = []
        for profile in profiles:
            screening.append(await run_profile(
                profile,
                scheduling_cases,
                routing_cases,
                business_cases,
                settings,
                http,
                args,
                1,
                True,
            ))

        finalists = sorted(screening, key=lambda item: item["score"], reverse=True)[: args.finalists]
        finalist_names = [item["profile"]["name"] for item in finalists]
        print(f"\nFinalists: {', '.join(finalist_names)}", flush=True)

        final_results: list[dict[str, Any]] = []
        for name in finalist_names:
            profile = next(item for item in profiles if item.name == name)
            final_results.append(await run_profile(
                profile,
                scheduling_cases,
                routing_cases,
                business_cases,
                settings,
                http,
                args,
                args.critical_repetitions,
                False,
            ))

    final_results.sort(key=lambda item: item["score"], reverse=True)
    best = final_results[0]
    report = {
        "model_label": args.model_label,
        "family": args.family,
        "model_api_name": args.model,
        "source": {
            "scheduling_cases": str(SCHEDULING_CASES),
            "routing_cases": str(ROUTING_CASES),
            "business_cases": str(BUSINESS_CASES),
        },
        "thresholds": {
            "schema_valid_rate": 0.99,
            "scheduling_semantic_accuracy": 0.95,
            "intent_accuracy": 0.95,
            "hallucinated_field_rate_max": 0.02,
            "routing_accuracy": 0.95,
            "false_scheduling_rate": 0.0,
            "business_accuracy": 0.90,
            "critical_pass_rate": 1.0,
        },
        "screening": [
            {
                "profile": item["profile"],
                "score": item["score"],
                "scheduling": {k: v for k, v in item["scheduling"].items() if k != "failures"},
                "routing": {k: v for k, v in item["routing"].items() if k != "failures"},
                "business": {k: v for k, v in item["business"].items() if k != "failures"},
            }
            for item in sorted(screening, key=lambda result: result["score"], reverse=True)
        ],
        "finalists": final_results,
        "best_profile": best["profile"],
        "best_sufficient": best["sufficient"],
        "decision": {
            "status": "model_sufficient" if best["sufficient"] else "model_insufficient",
            "next_step": (
                f"Use {args.model_label} with {best['profile']['name']}."
                if best["sufficient"]
                else "This model family/size does not meet the agent acceptance thresholds."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== FAMILY MODEL DIAGNOSTIC RESULT ===")
    print(json.dumps({
        "model_label": args.model_label,
        "family": args.family,
        "best_profile": best["profile"]["name"],
        "best_score": best["score"],
        "sufficient": best["sufficient"],
        "scheduling": {k: v for k, v in best["scheduling"].items() if k != "failures"},
        "routing": {k: v for k, v in best["routing"].items() if k != "failures"},
        "business": {k: v for k, v in best["business"].items() if k != "failures"},
        "decision": report["decision"],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
