from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare cross-family business representative diagnostics.")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "model_label" not in data or "family" not in data or "finalists" not in data:
        raise ValueError(f"Not a family model diagnostic report: {path}")
    data["_path"] = str(path)
    return data


def size_rank(label: str) -> float:
    normalized = label.casefold()
    match = re.search(r"(?:^|[^0-9.])(?:e)?(0\.8|1|2|3|4|7|8|9|12)b", normalized)
    if not match:
        return 999.0
    return float(match.group(1))


def rank_key(report: dict[str, Any]) -> tuple[float, float, float]:
    best = report["finalists"][0]
    combined_p95 = (
        best["scheduling"]["latency_ms"]["p95"]
        + best["routing"]["latency_ms"]["p95"]
        + best["business"]["latency_ms"]["p95"]
    )
    return size_rank(report["model_label"]), -best["score"], combined_p95


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    best = report["finalists"][0]
    return {
        "model": report["model_label"],
        "family": report["family"],
        "report": report["_path"],
        "best_profile": best["profile"]["name"],
        "sufficient": bool(best["sufficient"]),
        "score": best["score"],
        "scheduling_semantic_accuracy": best["scheduling"]["semantic_accuracy"],
        "intent_accuracy": best["scheduling"]["intent_accuracy"],
        "hallucinated_field_rate": best["scheduling"]["hallucinated_field_rate"],
        "routing_accuracy": best["routing"]["accuracy"],
        "false_scheduling_rate": best["routing"]["false_scheduling_rate"],
        "business_accuracy": best["business"]["accuracy"],
        "scheduling_p95_ms": best["scheduling"]["latency_ms"]["p95"],
        "routing_p95_ms": best["routing"]["latency_ms"]["p95"],
        "business_p95_ms": best["business"]["latency_ms"]["p95"],
    }


def verdict(reports: list[dict[str, Any]]) -> dict[str, Any]:
    passing = sorted(
        (report for report in reports if report["finalists"][0]["sufficient"]),
        key=rank_key,
    )
    if passing:
        selected = passing[0]
        best = selected["finalists"][0]
        return {
            "status": "selected_model",
            "selected_model": selected["model_label"],
            "selected_family": selected["family"],
            "selected_profile": best["profile"]["name"],
            "reason": "This is the smallest tested model that meets every routing, scheduling, business-grounding and critical-consistency threshold.",
        }

    ranked = sorted(reports, key=lambda report: report["finalists"][0]["score"], reverse=True)
    best = ranked[0]
    return {
        "status": "no_tested_model_sufficient",
        "selected_model": None,
        "selected_family": None,
        "selected_profile": None,
        "best_failed_model": best["model_label"],
        "best_failed_family": best["family"],
        "best_failed_score": best["finalists"][0]["score"],
        "reason": "None of the tested models meets all acceptance thresholds. Test the next size or revisit the bounded task/prompt before fine-tuning.",
    }


def main() -> int:
    args = parse_args()
    reports = [load(path) for path in args.reports]
    result = {
        "models": [summarize(report) for report in sorted(reports, key=rank_key)],
        "decision": verdict(reports),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
