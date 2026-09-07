from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
DEFAULT_CASES = Path(__file__).with_name("agent_cases.jsonl")
DEFAULT_RESULTS = Path(__file__).with_name("results") / "latest.json"
DEFAULT_QWENCLOUD = Path(__file__).with_name("results") / "qwencloud.jsonl"
SERVER_ENV = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class ExpectedCall:
    name: str
    arguments: dict[str, Any] | None


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    message: str
    context: list[dict[str, Any]]
    expected_calls: list[ExpectedCall]
    call_order: str
    completion: str


@dataclass(frozen=True)
class ObservedCall:
    name: str
    arguments: dict[str, Any] | None
    ok: bool | None


@dataclass(frozen=True)
class AgentRun:
    output: str
    calls: list[ObservedCall]
    trace: dict[str, Any] | None
    latency_ms: float
    error: str | None


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    run: AgentRun
    passed: bool
    selection_correct: bool
    arguments_correct: bool
    execution_correct: bool
    reasons: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end portfolio agent evaluation.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--qwencloud", type=Path, default=DEFAULT_QWENCLOUD)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--diagnostics-token", default=_diagnostics_token())
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        default=[],
        help="Run only the named case. Repeat this option to select multiple cases.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    seen: set[str] = set()

    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue

        payload = json.loads(raw)
        case_id = str(payload["id"]).strip()
        if not case_id or case_id in seen:
            raise ValueError(f"Invalid or duplicate id at {path}:{line_number}: {case_id!r}")

        call_order = str(payload.get("call_order", "exact"))
        if call_order not in {"exact", "any"}:
            raise ValueError(f"Invalid call_order for {case_id}: {call_order!r}")

        expected_calls = []
        for item in payload.get("expected_calls", []):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError(f"Invalid expected call for {case_id}: {item!r}")
            arguments = item.get("arguments")
            if arguments is not None and not isinstance(arguments, dict):
                raise ValueError(f"Invalid expected arguments for {case_id}: {arguments!r}")
            expected_calls.append(ExpectedCall(name=item["name"], arguments=arguments))

        cases.append(
            EvalCase(
                case_id=case_id,
                category=str(payload["category"]),
                message=str(payload["message"]).strip(),
                context=list(payload.get("context", [])),
                expected_calls=expected_calls,
                call_order=call_order,
                completion=str(payload.get("completion", "")).strip(),
            )
        )
        seen.add(case_id)

    if not cases:
        raise ValueError(f"No cases found in {path}")

    return cases


def select_cases(cases: list[EvalCase], case_ids: list[str]) -> list[EvalCase]:
    if not case_ids:
        return cases

    requested = set(case_ids)
    available = {case.case_id for case in cases}
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"Unknown eval case(s): {', '.join(missing)}")

    return [case for case in cases if case.case_id in requested]


async def run_agent(
    client: httpx.AsyncClient,
    base_url: str,
    case: EvalCase,
    diagnostics_token: str | None,
) -> AgentRun:
    started = time.perf_counter()
    output_parts: list[str] = []
    streamed_tools: list[ObservedCall] = []
    trace: dict[str, Any] | None = None
    error: str | None = None
    event_name: str | None = None
    headers = (
        {"x-agent-diagnostics-token": diagnostics_token}
        if diagnostics_token
        else None
    )

    async with client.stream(
        "POST",
        f"{base_url.rstrip('/')}/v1/chat/stream",
        json={"message": case.message, "context": case.context},
        headers=headers,
    ) as response:
        response.raise_for_status()

        async for line in response.aiter_lines():
            if not line:
                event_name = None
                continue

            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
                continue

            if not line.startswith("data:") or event_name is None:
                continue

            payload = json.loads(line.removeprefix("data:").strip())

            if event_name == "token":
                output_parts.append(str(payload.get("text", "")))
            elif event_name == "tool" and payload.get("state") == "running":
                streamed_tools.append(
                    ObservedCall(name=str(payload.get("name", "")), arguments=None, ok=None)
                )
            elif event_name == "trace":
                trace = payload
            elif event_name == "error":
                error = str(payload.get("message", "unknown error"))

    if diagnostics_token and trace is None and error is None:
        error = "diagnostic trace missing"

    calls = _calls_from_trace(trace) if trace is not None else streamed_tools
    return AgentRun(
        output="".join(output_parts).strip(),
        calls=calls,
        trace=trace,
        latency_ms=(time.perf_counter() - started) * 1000,
        error=error,
    )


def _calls_from_trace(trace: dict[str, Any]) -> list[ObservedCall]:
    calls: list[ObservedCall] = []
    for round_trace in trace.get("rounds", []):
        for call in round_trace.get("tool_calls", []):
            arguments = call.get("arguments")
            calls.append(
                ObservedCall(
                    name=str(call.get("name", "")),
                    arguments=arguments if isinstance(arguments, dict) else None,
                    ok=bool(call.get("ok")),
                )
            )
    return calls


def _selection_matches(case: EvalCase, calls: list[ObservedCall]) -> bool:
    expected = [call.name for call in case.expected_calls]
    actual = [call.name for call in calls]
    if case.call_order == "any":
        return Counter(expected) == Counter(actual)
    return expected == actual


def _arguments_subset(expected: dict[str, Any] | None, actual: dict[str, Any] | None) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    return all(actual.get(key) == value for key, value in expected.items())


def _arguments_match(case: EvalCase, calls: list[ObservedCall]) -> bool:
    if not _selection_matches(case, calls):
        return False

    if case.call_order == "exact":
        return all(
            _arguments_subset(expected.arguments, actual.arguments)
            for expected, actual in zip(case.expected_calls, calls, strict=True)
        )

    remaining = list(calls)
    for expected in case.expected_calls:
        index = next(
            (
                i
                for i, actual in enumerate(remaining)
                if actual.name == expected.name
                and _arguments_subset(expected.arguments, actual.arguments)
            ),
            None,
        )
        if index is None:
            return False
        remaining.pop(index)
    return not remaining


def _execution_matches(calls: list[ObservedCall]) -> bool:
    return all(call.ok is not False for call in calls)


def evaluate_case(case: EvalCase, run: AgentRun) -> CaseResult:
    reasons: list[str] = []
    selection_correct = _selection_matches(case, run.calls)
    arguments_correct = _arguments_match(case, run.calls)
    execution_correct = _execution_matches(run.calls)

    if run.error:
        reasons.append(f"agent error: {run.error}")

    if not run.output:
        reasons.append("empty final answer")

    if not selection_correct:
        reasons.append(
            "tools expected="
            f"{[call.name for call in case.expected_calls]!r} "
            f"actual={[call.name for call in run.calls]!r}"
        )
    elif not arguments_correct:
        reasons.append(
            "arguments expected="
            f"{[call.arguments for call in case.expected_calls]!r} "
            f"actual={[call.arguments for call in run.calls]!r}"
        )

    if not execution_correct:
        failed = [call.name for call in run.calls if call.ok is False]
        reasons.append(f"tool execution failures={failed!r}")

    return CaseResult(
        case=case,
        run=run,
        passed=not reasons,
        selection_correct=selection_correct,
        arguments_correct=arguments_correct,
        execution_correct=execution_correct,
        reasons=reasons,
    )


async def evaluate_all(
    cases: list[EvalCase],
    *,
    base_url: str,
    timeout: float,
    diagnostics_token: str | None,
) -> list[CaseResult]:
    timeout_config = httpx.Timeout(timeout)
    async with httpx.AsyncClient(timeout=timeout_config) as client:
        results: list[CaseResult] = []
        for index, case in enumerate(cases, start=1):
            try:
                run = await run_agent(client, base_url, case, diagnostics_token)
            except Exception as exc:
                run = AgentRun(
                    output="",
                    calls=[],
                    trace=None,
                    latency_ms=0.0,
                    error=f"{type(exc).__name__}: {exc}",
                )

            result = evaluate_case(case, run)
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            print(
                f"[{index:02d}/{len(cases):02d}] {status} "
                f"{case.case_id} tools={[call.name for call in run.calls]} "
                f"{run.latency_ms:.0f}ms"
            )
            _print_trace(run.trace)
            for reason in result.reasons:
                print(f"  - {reason}")

        return results


def build_summary(results: list[CaseResult]) -> dict[str, Any]:
    passed = sum(result.passed for result in results)
    selection_correct = sum(result.selection_correct for result in results)
    execution_correct = sum(result.execution_correct for result in results)
    answers_present = sum(bool(result.run.output) for result in results)
    parameter_cases = [
        result
        for result in results
        if any(call.arguments is not None for call in result.case.expected_calls)
    ]
    parameter_correct = sum(result.arguments_correct for result in parameter_cases)
    latencies = [result.run.latency_ms for result in results if result.run.latency_ms > 0]

    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        by_category[result.case.category].append(result)

    return {
        "cases": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": passed / len(results),
        "tool_selection_correct": selection_correct,
        "tool_selection_rate": selection_correct / len(results),
        "parameter_extraction_cases": len(parameter_cases),
        "parameter_extraction_correct": parameter_correct,
        "parameter_extraction_rate": (
            parameter_correct / len(parameter_cases) if parameter_cases else None
        ),
        "tool_execution_success_cases": execution_correct,
        "tool_execution_success_rate": execution_correct / len(results),
        "answers_present": answers_present,
        "answer_presence_rate": answers_present / len(results),
        "latency_p50_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": percentile(latencies, 0.95) if latencies else None,
        "by_category": {
            category: {
                "cases": len(items),
                "passed": sum(item.passed for item in items),
                "pass_rate": sum(item.passed for item in items) / len(items),
            }
            for category, items in sorted(by_category.items())
        },
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values must not be empty")
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def write_outputs(
    results: list[CaseResult],
    *,
    results_path: Path,
    qwencloud_path: Path,
) -> dict[str, Any]:
    summary = build_summary(results)

    results_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "cases": [
            {
                "id": result.case.case_id,
                "category": result.case.category,
                "passed": result.passed,
                "reasons": result.reasons,
                "expected_calls": [
                    {"name": call.name, "arguments": call.arguments}
                    for call in result.case.expected_calls
                ],
                "actual_calls": [
                    {"name": call.name, "arguments": call.arguments, "ok": call.ok}
                    for call in result.run.calls
                ],
                "latency_ms": round(result.run.latency_ms, 2),
                "output": result.run.output,
                "completion": result.case.completion,
                "trace": result.run.trace,
            }
            for result in results
        ],
    }
    results_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with qwencloud_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(
                    {
                        "prompt": result.case.message,
                        "output": result.run.output,
                        "completion": result.case.completion,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("\nAGENT LIVE EVAL")
    print(f"cases: {summary['cases']}")
    print(f"pass: {summary['passed']}/{summary['cases']} ({summary['pass_rate']:.1%})")
    print(
        "tool selection: "
        f"{summary['tool_selection_correct']}/{summary['cases']} "
        f"({summary['tool_selection_rate']:.1%})"
    )

    parameter_rate = summary["parameter_extraction_rate"]
    if parameter_rate is None:
        print("parameter extraction: n/a")
    else:
        print(
            "parameter extraction: "
            f"{summary['parameter_extraction_correct']}/"
            f"{summary['parameter_extraction_cases']} "
            f"({parameter_rate:.1%})"
        )

    print(
        "tool execution success: "
        f"{summary['tool_execution_success_cases']}/{summary['cases']} "
        f"({summary['tool_execution_success_rate']:.1%})"
    )
    print(
        f"latency p50: {summary['latency_p50_ms']:.0f} ms"
        if summary["latency_p50_ms"] is not None
        else "latency p50: n/a"
    )
    print(
        f"latency p95: {summary['latency_p95_ms']:.0f} ms"
        if summary["latency_p95_ms"] is not None
        else "latency p95: n/a"
    )

    print("\nby category:")
    for category, item in summary["by_category"].items():
        print(f"  {category}: {item['passed']}/{item['cases']} ({item['pass_rate']:.1%})")


def _print_trace(trace: dict[str, Any] | None) -> None:
    if not trace:
        return

    for round_trace in trace.get("rounds", []):
        response = round_trace.get("response", {})
        print(
            f"  round={round_trace.get('round')} finish={response.get('finish_reason')} "
            f"duration_ms={response.get('duration_ms')} "
            f"usage={response.get('usage')} timings={response.get('timings')}"
        )
        for call in round_trace.get("tool_calls", []):
            arguments = json.dumps(
                call.get("arguments"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            print(
                f"    tool={call.get('name')} args={arguments} ok={call.get('ok')} "
                f"duration_ms={call.get('duration_ms')}"
            )


def _diagnostics_token() -> str | None:
    value = os.getenv("AGENT_DIAGNOSTICS_TOKEN")
    if value and value.strip():
        return value.strip()

    if not SERVER_ENV.exists():
        return None

    for raw in SERVER_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != "AGENT_DIAGNOSTICS_TOKEN":
            continue
        value = value.strip().strip('"').strip("'")
        return value or None
    return None


async def async_main() -> int:
    args = parse_args()
    cases = select_cases(load_cases(args.cases), args.case_ids)
    results = await evaluate_all(
        cases,
        base_url=args.base_url,
        timeout=args.timeout,
        diagnostics_token=args.diagnostics_token,
    )
    summary = write_outputs(
        results,
        results_path=args.results,
        qwencloud_path=args.qwencloud,
    )
    print_summary(summary)

    print(f"\nfull results: {args.results}")
    print(f"QwenCloud inference results: {args.qwencloud}")

    if args.strict and summary["failed"]:
        return 1
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
