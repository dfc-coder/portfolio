from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from app.reranker import Reranker
from app.tool_search import ToolSearch, tool_name
from run_agent_eval import DEFAULT_CASES, load_cases

DEFAULT_BASE_URL = os.getenv("RERANKER_EVAL_URL", "http://localhost:8082")
DEFAULT_MODEL = os.getenv("RERANKER_MODEL", "Qwen3-Reranker-0.6B")
DEFAULT_TIMEOUT = float(os.getenv("RERANKER_TIMEOUT_SECONDS", "30"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate live tool search against agent eval cases.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases)
    reranker = Reranker(args.base_url, model=args.model, timeout_seconds=args.timeout)
    search = ToolSearch(reranker)

    failed_cases = 0
    missing_total = 0
    extra_total = 0
    try:
        for index, case in enumerate(cases, start=1):
            selection = await search.select(case.message, case.context)
            selected = {tool_name(tool) for tool in selection.tools}
            expected = {call.name for call in case.expected_calls}
            missing = sorted(expected - selected)
            extra = sorted(selected - expected)
            failed = bool(missing or extra)
            failed_cases += int(failed)
            missing_total += len(missing)
            extra_total += len(extra)

            status = "FAIL" if failed else "PASS"
            print(
                f"[{index:02d}/{len(cases):02d}] {status} {case.case_id} "
                f"selected={sorted(selected)} expected={sorted(expected)}"
            )
            if missing:
                print(f"  missing required tool(s): {missing}")
            if extra:
                print(f"  unexpected tool(s): {extra}")
            print(f"  scores={selection.scores}")
    finally:
        await reranker.close()

    print()
    print(f"cases={len(cases)}")
    print(f"passed={len(cases) - failed_cases}")
    print(f"failed={failed_cases}")
    print(f"missing_required_tools={missing_total}")
    print(f"unexpected_tools={extra_total}")
    print("gate=PASS" if failed_cases == 0 else "gate=FAIL")

    if args.strict and failed_cases:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
