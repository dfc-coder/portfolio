from __future__ import annotations

import asyncio

from run_agent_eval import (
    evaluate_all,
    load_cases,
    parse_args,
    print_summary,
    select_cases,
    write_outputs,
)


async def async_main() -> int:
    args = parse_args()
    cases = select_cases(load_cases(args.cases), args.case_ids)
    results = []

    for case in cases:
        current = await evaluate_all(
            [case],
            base_url=args.base_url,
            timeout=args.timeout,
            diagnostics_token=args.diagnostics_token,
        )
        results.extend(current)
        if current and not current[0].passed:
            print("strict gate: stopping on first failure")
            break

    summary = write_outputs(
        results,
        results_path=args.results,
        qwencloud_path=args.qwencloud,
    )
    print_summary(summary)

    print(f"\nfull results: {args.results}")
    print(f"QwenCloud inference results: {args.qwencloud}")
    return 1 if summary["failed"] else 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
