from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from app.agent.prompts import CONVERSATION_PROMPT_ID, PORTFOLIO_PROMPT_ID
from app.agent.responder import Responder
from app.agent.scheduler import Scheduler
from app.domain.conversation import ChatTurn, SessionState
from app.domain.routing import Route
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.ports.llm import GenerationConfig, LlmPort
from app.portfolio.search import Fact, PortfolioSearch
from app.scheduling.policy import SchedulingPolicy
from tests.evals.evaluation_report import report_metadata
from tests.evals.responses.grader import (
    ResponseCase,
    deterministic_grade,
    load_response_cases,
    semantic_grade,
)


@dataclass(frozen=True)
class PromptRun:
    response: str
    evidence: tuple[Fact, ...]
    prompt_id: str
    generation_latency_ms: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate current response quality.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/evals/responses/cases.jsonl"),
    )
    parser.add_argument(
        "--portfolio-only",
        action="store_true",
        help="Evaluate only portfolio response cases.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 1.0


def rate(records: list[dict[str, Any]], predicate: Any) -> float:
    if not records:
        return 1.0
    return round(sum(bool(predicate(record)) for record in records) / len(records), 4)


def prompt_id_for(route: Route) -> str:
    return PORTFOLIO_PROMPT_ID if route == Route.PORTFOLIO else CONVERSATION_PROMPT_ID


async def run_prompt(
    case: ResponseCase,
    *,
    responder: Responder,
    portfolio: PortfolioSearch,
) -> PromptRun:
    """Run one response case through the same path used by the agent."""
    route = Route(case.route)
    state = SessionState(session_id=f"response-eval-{case.case_id}")
    state.current_focus = route
    state.turns.append(ChatTurn(role="user", content=case.message))

    evidence: tuple[Fact, ...] = ()
    if route == Route.PORTFOLIO:
        evidence = (await portfolio.search(case.message)).facts

    started = time.perf_counter()
    response = "".join(
        [
            chunk
            async for chunk in responder.stream(
                state,
                evidence=evidence,
            )
        ]
    )
    generation_latency_ms = (time.perf_counter() - started) * 1000

    return PromptRun(
        response=response,
        evidence=evidence,
        prompt_id=prompt_id_for(route),
        generation_latency_ms=generation_latency_ms,
    )


async def run_test_case(
    case: ResponseCase,
    *,
    responder: Responder,
    portfolio: PortfolioSearch,
    grader_llm: LlmPort,
) -> dict[str, Any]:
    """Run one case, grade its output, and return a structured result."""
    prompt_run = await run_prompt(
        case,
        responder=responder,
        portfolio=portfolio,
    )

    deterministic = deterministic_grade(case, prompt_run.response)
    semantic_evidence = tuple(fact.text for fact in prompt_run.evidence)
    if case.route == Route.PORTFOLIO.value:
        semantic_evidence += tuple(
            f"AGENT_CAPABILITY: {capability}"
            for capability in Scheduler.PUBLIC_CAPABILITIES
        )

    grader_started = time.perf_counter()
    semantic = await semantic_grade(
        grader_llm,
        case=case,
        response=prompt_run.response,
        evidence=semantic_evidence,
    )
    grader_latency_ms = (time.perf_counter() - grader_started) * 1000

    hard_contract_pass = (
        deterministic.non_empty
        and deterministic.forbidden_ok
        and deterministic.length_ok
        and semantic.language_ok
        and semantic.identity_ok
        and semantic.action_safety_ok
    )

    return {
        "case_id": case.case_id,
        "critical": case.critical,
        "message": case.message,
        "route": case.route,
        "language": case.language,
        "prompt_id": prompt_run.prompt_id,
        "response": prompt_run.response,
        "evidence_sources": [fact.source for fact in prompt_run.evidence],
        "deterministic": {
            **asdict(deterministic),
            "passed": deterministic.passed,
        },
        "semantic": semantic.model_dump(),
        "hard_contract_pass": hard_contract_pass,
        "latency_ms": {
            "generation": round(prompt_run.generation_latency_ms, 2),
            "grader": round(grader_latency_ms, 2),
        },
    }


async def run_eval(
    cases: list[ResponseCase],
    *,
    responder: Responder,
    portfolio: PortfolioSearch,
    grader_llm: LlmPort,
) -> list[dict[str, Any]]:
    """Run every response case and collect one structured result per case."""
    records: list[dict[str, Any]] = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        print(
            f"[response] case {index}/{total} {case.case_id} ...",
            file=sys.stderr,
            flush=True,
        )
        record = await run_test_case(
            case,
            responder=responder,
            portfolio=portfolio,
            grader_llm=grader_llm,
        )
        records.append(record)
        latency = record["latency_ms"]
        print(
            f"[response] case {index}/{total} {case.case_id} "
            f"done generation={latency['generation']:.0f}ms grader={latency['grader']:.0f}ms "
            f"hard={'PASS' if record['hard_contract_pass'] else 'FAIL'}",
            file=sys.stderr,
            flush=True,
        )
    return records


async def evaluate(
    cases_path: Path,
    settings: Settings,
    *,
    portfolio_only: bool = False,
) -> dict[str, Any]:
    cases = load_response_cases(cases_path)
    if portfolio_only:
        cases = [case for case in cases if case.route == Route.PORTFOLIO.value]
    if not cases:
        raise ValueError("response evaluation selected no cases")

    profile = load_business_profile(settings.profile_path)
    policy = SchedulingPolicy(profile.scheduling)
    generation_config = GenerationConfig(
        temperature=settings.renderer_temperature,
        max_tokens=settings.renderer_max_tokens,
        top_p=0.9,
        top_k=20,
    )

    grader_base_url = os.getenv("EVAL_GRADER_BASE_URL", settings.llama_base_url)
    grader_model = os.getenv("EVAL_GRADER_MODEL", settings.llama_model)

    async with (
        httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as response_http,
        httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as grader_http,
        httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as embedding_http,
    ):
        response_llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=response_http,
        )
        grader_llm = LlamaCppClient(
            grader_base_url,
            grader_model,
            settings.llama_timeout_seconds,
            client=grader_http,
        )
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=embedding_http,
        )
        portfolio = PortfolioSearch(
            profile,
            embeddings,
            max_chars=settings.context_max_chars,
            max_documents=settings.context_max_documents,
            min_score=settings.portfolio_min_score,
        )
        responder = Responder(
            response_llm,
            profile,
            policy,
            generation_config,
            Scheduler.PUBLIC_CAPABILITIES,
        )
        await portfolio.warm()

        records = await run_eval(
            cases,
            responder=responder,
            portfolio=portfolio,
            grader_llm=grader_llm,
        )

    semantic_records = [record["semantic"] for record in records]
    candidate_id = PORTFOLIO_PROMPT_ID if portfolio_only else "current-response-prompts"
    report: dict[str, Any] = {
        "metadata": report_metadata(
            dataset=cases_path,
            candidate_id=candidate_id,
            model=settings.llama_model,
            generation_config={
                "temperature": generation_config.temperature,
                "max_tokens": generation_config.max_tokens,
                "top_p": generation_config.top_p,
                "top_k": generation_config.top_k,
            },
        ),
        "prompts": {
            "conversation": CONVERSATION_PROMPT_ID,
            "portfolio": PORTFOLIO_PROMPT_ID,
        },
        "scope": "portfolio" if portfolio_only else "all_response_routes",
        "grader_model": grader_model,
        "cases": len(records),
        "metrics": {
            "hard_contract_pass_rate": rate(
                records, lambda record: record["hard_contract_pass"]
            ),
            "required_content_pass_rate": rate(
                records, lambda record: record["deterministic"]["required_groups_ok"]
            ),
            "relevance": mean([float(item["relevance"]) for item in semantic_records]),
            "groundedness": mean([float(item["groundedness"]) for item in semantic_records]),
            "completeness": mean([float(item["completeness"]) for item in semantic_records]),
            "language_pass_rate": rate(
                records, lambda record: record["semantic"]["language_ok"]
            ),
            "identity_pass_rate": rate(
                records, lambda record: record["semantic"]["identity_ok"]
            ),
            "action_safety_pass_rate": rate(
                records, lambda record: record["semantic"]["action_safety_ok"]
            ),
            "critical_hard_contract_failures": sum(
                record["critical"] and not record["hard_contract_pass"]
                for record in records
            ),
        },
        "records": records,
    }
    return report


def strict_pass(report: dict[str, Any]) -> bool:
    metrics = report["metrics"]
    return (
        metrics["hard_contract_pass_rate"] == 1.0
        and metrics["language_pass_rate"] == 1.0
        and metrics["identity_pass_rate"] == 1.0
        and metrics["action_safety_pass_rate"] == 1.0
        and metrics["critical_hard_contract_failures"] == 0
    )


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    report = await evaluate(
        args.cases,
        settings,
        portfolio_only=args.portfolio_only,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not args.strict or strict_pass(report) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
