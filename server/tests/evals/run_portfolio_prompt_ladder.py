from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.agent.context import PORTFOLIO_PROMPT_VERSIONS
from app.infrastructure.config.settings import Settings
from tests.evals.compare_reports import compare
from tests.evals.run_response_eval import evaluate, strict_pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the portfolio prompt progression v1 -> v4 on the same portfolio response cases.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/evals/responses/cases.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/evals/reports/portfolio-prompts"),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail only when the final v4 hard contracts fail. Earlier versions remain measurable baselines.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def run_ladder(
    cases: Path,
    output_dir: Path,
    settings: Settings,
) -> dict[str, Any]:
    reports: dict[str, dict[str, Any]] = {}
    total_versions = len(PORTFOLIO_PROMPT_VERSIONS)

    for index, version in enumerate(PORTFOLIO_PROMPT_VERSIONS, start=1):
        started = time.perf_counter()
        print(
            f"=== portfolio-{version} ({index}/{total_versions}) ===",
            file=sys.stderr,
            flush=True,
        )
        report = await evaluate(
            cases,
            settings,
            portfolio_prompt_version=version,
            portfolio_only=True,
        )
        reports[version] = report
        report_path = output_dir / f"portfolio-{version}.json"
        write_json(report_path, report)
        elapsed = time.perf_counter() - started
        print(
            f"=== portfolio-{version} complete in {elapsed:.1f}s -> {report_path} ===",
            file=sys.stderr,
            flush=True,
        )

    comparisons = [
        compare(reports["v1"], reports["v2"]),
        compare(reports["v2"], reports["v3"]),
        compare(reports["v3"], reports["v4"]),
        compare(reports["v1"], reports["v4"]),
    ]
    summary = {
        "sequence": ["portfolio-v1", "portfolio-v2", "portfolio-v3", "portfolio-v4"],
        "changes": {
            "portfolio-v1": "baseline prompt from the previous HEAD",
            "portfolio-v2": "v1 plus a clear, direct, task-first opening instruction",
            "portfolio-v3": "v2 semantics plus XML boundaries for dynamic data",
            "portfolio-v4": "v3 plus three synthetic few-shot examples for grounded answer, missing evidence, and capability-without-side-effect behavior",
        },
        "reports": {
            version: str(output_dir / f"portfolio-{version}.json")
            for version in PORTFOLIO_PROMPT_VERSIONS
        },
        "comparisons": comparisons,
        "final_hard_contracts_pass": strict_pass(reports["v4"]),
    }
    summary_path = output_dir / "summary.json"
    write_json(summary_path, summary)
    print(f"summary -> {summary_path}", file=sys.stderr, flush=True)
    return summary


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    summary = await run_ladder(args.cases, args.output_dir, settings)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.strict and not summary["final_hard_contracts_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
