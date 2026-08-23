from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Qwen3.5 diagnostic reports and choose the smallest sufficient model.")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "model_label" not in data or "finalists" not in data:
        raise ValueError(f"Not a model diagnostic report: {path}")
    data["_path"] = str(path)
    return data


def size_rank(label: str) -> int:
    normalized = label.lower()
    for rank, token in enumerate(("0.8b", "2b", "4b", "9b")):
        if token in normalized:
            return rank
    return 99


def rank_key(report: dict[str, Any]) -> tuple[int, float, float]:
    best = report["finalists"][0]
    return size_rank(report["model_label"]), -best["score"], best["scheduling"]["latency_ms"]["p95"]


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    best = report["finalists"][0]
    return {
        "model": report["model_label"],
        "report": report["_path"],
        "best_profile": best["profile"]["name"],
        "sufficient": bool(best["sufficient"]),
        "score": best["score"],
        "scheduling_semantic_accuracy": best["scheduling"]["semantic_accuracy"],
        "intent_accuracy": best["scheduling"]["intent_accuracy"],
        "hallucinated_field_rate": best["scheduling"]["hallucinated_field_rate"],
        "routing_accuracy": best["routing"]["accuracy"],
        "false_scheduling_rate": best["routing"]["false_scheduling_rate"],
        "scheduling_p95_ms": best["scheduling"]["latency_ms"]["p95"],
        "routing_p95_ms": best["routing"]["latency_ms"]["p95"],
    }


def verdict(reports: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(reports, key=rank_key)
    passing = [report for report in ordered if report["finalists"][0]["sufficient"]]
    baseline = next((r for r in ordered if "0.8b" in r["model_label"].lower()), ordered[0])
    baseline_best = baseline["finalists"][0]

    if baseline_best["sufficient"]:
        return {
            "status": "configure_current_model",
            "selected_model": baseline["model_label"],
            "selected_profile": baseline_best["profile"]["name"],
            "reason": "The 0.8B model meets every agent-critical threshold under at least one tested configuration.",
        }

    if passing:
        selected = passing[0]
        best = selected["finalists"][0]
        return {
            "status": "change_model",
            "selected_model": selected["model_label"],
            "selected_profile": best["profile"]["name"],
            "reason": "The 0.8B model fails while a larger Qwen3.5 model passes the identical corpus and configuration search.",
        }

    tested_ranks = {size_rank(report["model_label"]) for report in ordered}
    if 0 not in tested_ranks:
        return {
            "status": "missing_baseline",
            "selected_model": None,
            "selected_profile": None,
            "reason": "Benchmark Qwen3.5-0.8B so configuration-vs-size can be determined against the current baseline.",
        }
    if 1 not in tested_ranks:
        return {
            "status": "benchmark_2b",
            "selected_model": None,
            "selected_profile": None,
            "reason": "No 0.8B configuration is sufficient. Run the identical benchmark against Qwen3.5-2B.",
        }
    if 2 not in tested_ranks:
        return {
            "status": "benchmark_4b",
            "selected_model": None,
            "selected_profile": None,
            "reason": "0.8B and 2B both fail. Run Qwen3.5-4B once before concluding that scale does not solve the task.",
        }

    largest = max(ordered, key=lambda report: size_rank(report["model_label"]))
    return {
        "status": "configuration_and_scale_insufficient_up_to_4b",
        "selected_model": None,
        "selected_profile": None,
        "reason": (
            f"No tested inference configuration passes on 0.8B, 2B, or {largest['model_label']}. "
            "Stop tuning sampling parameters; redesign the task contract/prompt or evaluate targeted fine-tuning."
        ),
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
