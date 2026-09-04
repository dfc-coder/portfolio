from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare numeric metrics from two eval reports.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    return parser.parse_args()


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"report must be a JSON object: {path}")
    return payload


def numeric_metrics(report: dict[str, Any]) -> dict[str, float]:
    metrics = report.get("metrics", report)
    if not isinstance(metrics, dict):
        raise ValueError("report metrics must be a JSON object")
    return {
        str(key): float(value)
        for key, value in metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def candidate_id(report: dict[str, Any], fallback: str) -> str:
    metadata = report.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("candidate_id")
        if isinstance(value, str) and value:
            return value
    return fallback


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_metrics = numeric_metrics(baseline)
    candidate_metrics = numeric_metrics(candidate)
    shared = sorted(set(baseline_metrics) & set(candidate_metrics))
    if not shared:
        raise ValueError("reports have no shared numeric metrics")
    return {
        "baseline": candidate_id(baseline, "baseline"),
        "candidate": candidate_id(candidate, "candidate"),
        "metrics": {
            key: {
                "baseline": baseline_metrics[key],
                "candidate": candidate_metrics[key],
                "delta": round(candidate_metrics[key] - baseline_metrics[key], 6),
            }
            for key in shared
        },
    }


def main() -> int:
    args = parse_args()
    result = compare(load_report(args.baseline), load_report(args.candidate))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
