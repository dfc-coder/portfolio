from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import httpx

from app.infrastructure.config.settings import Settings
from tests.evals import run_family_model_diagnostic as diagnostic


CRITICAL_GATE = 0.80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-fast cross-family model selection for the portfolio representative.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="benchmark-model")
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--family", choices=("qwen35", "gemma4"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser.parse_args()


def profiles_for(family: str) -> tuple[diagnostic.InferenceProfile, ...]:
    if family == "qwen35":
        # Exact Unsloth small-model Instruct / non-thinking / general-task profile.
        return tuple(
            profile
            for profile in diagnostic.QWEN35_PROFILES
            if profile.name == "qwen_unsloth_instruct_general"
        )
    return diagnostic.GEMMA4_PROFILES


def critical_gate(result: dict) -> tuple[bool, list[str]]:
    s = result["scheduling"]
    r = result["routing"]
    b = result["business"]
    failures: list[str] = []

    if s["schema_valid_rate"] < 0.99:
        failures.append(f"scheduling schema_valid_rate={s['schema_valid_rate']:.4f} < 0.99")
    if r["schema_valid_rate"] < 0.99:
        failures.append(f"routing schema_valid_rate={r['schema_valid_rate']:.4f} < 0.99")
    if s["critical_pass_rate"] < CRITICAL_GATE:
        failures.append(
            f"scheduling critical_pass_rate={s['critical_pass_rate']:.4f} < {CRITICAL_GATE:.2f}",
        )
    if r["critical_pass_rate"] < CRITICAL_GATE:
        failures.append(
            f"routing critical_pass_rate={r['critical_pass_rate']:.4f} < {CRITICAL_GATE:.2f}",
        )
    if b["critical_pass_rate"] < CRITICAL_GATE:
        failures.append(
            f"business critical_pass_rate={b['critical_pass_rate']:.4f} < {CRITICAL_GATE:.2f}",
        )
    return not failures, failures


def compact(result: dict) -> dict:
    return {
        "profile": result["profile"],
        "score": result["score"],
        "scheduling": {k: v for k, v in result["scheduling"].items() if k != "failures"},
        "routing": {k: v for k, v in result["routing"].items() if k != "failures"},
        "business": {k: v for k, v in result["business"].items() if k != "failures"},
    }


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    scheduling_cases = diagnostic.load_jsonl(diagnostic.SCHEDULING_CASES)
    routing_cases = diagnostic.load_jsonl(diagnostic.ROUTING_CASES, "routing")
    business_cases = diagnostic.load_jsonl(diagnostic.BUSINESS_CASES)
    profiles = profiles_for(args.family)
    if not profiles:
        raise RuntimeError(f"No benchmark profile configured for family={args.family}")

    critical_counts = {
        "scheduling": sum(bool(case.get("critical")) for case in scheduling_cases),
        "routing": sum(bool(case.get("critical")) for case in routing_cases),
        "business": sum(bool(case.get("critical")) for case in business_cases),
    }
    full_counts = {
        "scheduling": len(scheduling_cases),
        "routing": len(routing_cases),
        "business": len(business_cases),
    }
    critical_calls = sum(critical_counts.values())
    full_calls = sum(full_counts.values())

    print("\n=== MODEL SELECTION PROTOCOL ===", flush=True)
    print(f"Critical gate: {critical_calls} calls = {critical_counts}", flush=True)
    print(f"Full corpus (only if gate passes): {full_calls} calls = {full_counts}", flush=True)
    print(f"Maximum calls for one Qwen candidate: {critical_calls + full_calls}", flush=True)
    print("No repeated x5 reliability run is performed during model selection.\n", flush=True)

    timeout = max(settings.llama_timeout_seconds, 120.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        probe = diagnostic.FamilyLlm(
            http,
            args.base_url,
            args.model,
            profiles[0],
            args.max_tokens,
            args.family,
        )
        if not await probe.health():
            raise RuntimeError(f"Model server is not healthy at {args.base_url}")

        # Stage 1: one pass over critical cases only. Reject clearly weak candidates early.
        screenings: list[dict] = []
        for profile in profiles:
            result = await diagnostic.run_profile(
                profile,
                scheduling_cases,
                routing_cases,
                business_cases,
                settings,
                http,
                args,
                1,
                True,
            )
            screenings.append(result)

        best_screen = max(screenings, key=lambda item: item["score"])
        gate_ok, gate_failures = critical_gate(best_screen)
        if not gate_ok:
            report = {
                "model_label": args.model_label,
                "family": args.family,
                "protocol": "fail_fast_model_selection",
                "profile": asdict(profiles[0]) if len(profiles) == 1 else None,
                "calls": {
                    "executed": critical_calls * len(profiles),
                    "critical_gate_per_profile": critical_calls,
                    "full_corpus_skipped": True,
                },
                "screening": [compact(item) for item in screenings],
                "decision": {
                    "status": "model_rejected_at_critical_gate",
                    "gate_threshold": CRITICAL_GATE,
                    "failures": gate_failures,
                    "reason": (
                        "The model is too far below the acceptance target on critical cases; "
                        "running hundreds of additional/repeated calls would not change the selection decision."
                    ),
                },
            }
            write_report(args.output, report)
            print("\n=== MODEL REJECTED AT CRITICAL GATE ===")
            print(json.dumps(report["decision"], ensure_ascii=False, indent=2))
            print(f"Report: {args.output}")
            return 0

        # Stage 2: one full-corpus pass. Reliability repetitions are intentionally separate
        # and should only be run for the selected winner, not every candidate.
        profile = max(screenings, key=lambda item: item["score"])["profile"]["name"]
        selected_profile = next(item for item in profiles if item.name == profile)
        full_result = await diagnostic.run_profile(
            selected_profile,
            scheduling_cases,
            routing_cases,
            business_cases,
            settings,
            http,
            args,
            1,
            False,
        )

    is_sufficient = diagnostic.sufficient(full_result)
    report = {
        "model_label": args.model_label,
        "family": args.family,
        "protocol": "fail_fast_model_selection",
        "profile": full_result["profile"],
        "calls": {
            "executed": critical_calls * len(profiles) + full_calls,
            "critical_gate_per_profile": critical_calls,
            "full_corpus": full_calls,
            "reliability_repetitions": 0,
        },
        "screening": [compact(item) for item in screenings],
        "full_result": full_result,
        "decision": {
            "status": "model_sufficient_single_pass" if is_sufficient else "model_insufficient",
            "next_step": (
                "Compare against the other candidate; run repeated critical reliability only on the selected winner."
                if is_sufficient
                else "This model does not meet the full-corpus acceptance thresholds."
            ),
        },
    }
    write_report(args.output, report)
    print("\n=== MODEL SELECTION RESULT ===")
    print(json.dumps({
        "model_label": args.model_label,
        "profile": full_result["profile"]["name"],
        "sufficient_single_pass": is_sufficient,
        "scheduling": compact(full_result)["scheduling"],
        "routing": compact(full_result)["routing"],
        "business": compact(full_result)["business"],
        "decision": report["decision"],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
