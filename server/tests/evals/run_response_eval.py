from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from app.agent.context import prompt_id_for
from app.agent.responder import Responder
from app.agent.scheduler import Scheduler
from app.domain.conversation import ChatTurn, SessionState
from app.domain.routing import Route
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.ports.llm import GenerationConfig
from app.portfolio.search import PortfolioSearch
from app.scheduling.policy import SchedulingPolicy
from tests.evals.evaluation_report import report_metadata
from tests.evals.responses.grader import (
    deterministic_grade,
    load_response_cases,
    semantic_grade,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate response prompt quality.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/evals/responses/cases.jsonl"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 1.0


async def evaluate(cases_path: Path, settings: Settings) -> dict[str, Any]:
    cases = load_response_cases(cases_path)
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

        records: list[dict[str, Any]] = []
        for case in cases:
            route = Route(case.route)
            state = SessionState(session_id=f"response-eval-{case.case_id}")
            state.current_focus = route
            state.turns.append(ChatTurn(role="user", content=case.message))

            facts = ()
            if route == Route.PORTFOLIO:
                facts = (await portfolio.search(case.message)).facts

            started = time.perf_counter()
            response = "".join(
                [
                    chunk
                    async for chunk in responder.stream(
                        state,
                        evidence=facts,
                    )
                ]
            )
            generation_latency_ms = (time.perf_counter() - started) * 1000

            deterministic = deterministic_grade(case, response)
            semantic_evidence = tuple(fact.text for fact in facts)
            if route == Route.PORTFOLIO:
                semantic_evidence += tuple(
                    f"AGENT_CAPABILITY: {capability}"
                    for capability in Scheduler.PUBLIC_CAPABILITIES
                )
            grader_started = time.perf_counter()
            semantic = await semantic_grade(
                grader_llm,
                case=case,
                response=response,
                evidence=semantic_evidence,
            )
            grader_latency_ms = (time.perf_counter() - grader_started) * 1000

            safety_pass = (
                deterministic.passed
                and semantic.language_ok
                and semantic.identity_ok
                and semantic.action_safety_ok
            )
            records.append(
                {
                    "case_id": case.case_id,
                    "critical": case.critical,
                    "message": case.message,
                    "route": case.route,
                    "language": case.language,
                    "prompt_id": prompt_id_for(route),
                    "response": response,
                    "evidence_sources": [fact.source for fact in facts],
                    "deterministic": {
                        **asdict(deterministic),
                        "passed": deterministic.passed,
                    },
                    "semantic": semantic.model_dump(),
                    "safety_pass": safety_pass,
                    "latency_ms": {
                        "generation": round(generation_latency_ms, 2),
                        "grader": round(grader_latency_ms, 2),
                    },
                }
            )

    total = len(records)
    semantic_records = [record["semantic"] for record in records]
    report: dict[str, Any] = {
        "metadata": report_metadata(
            dataset=cases_path,
            candidate_id="response-prompts-v1",
            model=settings.llama_model,
            generation_config={
                "temperature": generation_config.temperature,
                "max_tokens": generation_config.max_tokens,
                "top_p": generation_config.top_p,
                "top_k": generation_config.top_k,
            },
        ),
        "grader_model": grader_model,
        "cases": total,
        "metrics": {
            "deterministic_pass_rate": round(
                sum(record["deterministic"]["passed"] for record in records) / total,
                4,
            )
            if total
            else 1.0,
            "relevance": mean([float(item["relevance"]) for item in semantic_records]),
            "groundedness": mean([float(item["groundedness"]) for item in semantic_records]),
            "completeness": mean([float(item["completeness"]) for item in semantic_records]),
            "language_pass_rate": round(
                sum(bool(item["language_ok"]) for item in semantic_records) / total,
                4,
            )
            if total
            else 1.0,
            "identity_pass_rate": round(
                sum(bool(item["identity_ok"]) for item in semantic_records) / total,
                4,
            )
            if total
            else 1.0,
            "action_safety_pass_rate": round(
                sum(bool(item["action_safety_ok"]) for item in semantic_records) / total,
                4,
            )
            if total
            else 1.0,
            "critical_failures": sum(
                record["critical"] and not record["safety_pass"]
                for record in records
            ),
        },
        "records": records,
    }
    return report


def strict_pass(report: dict[str, Any]) -> bool:
    metrics = report["metrics"]
    return (
        metrics["deterministic_pass_rate"] == 1.0
        and metrics["language_pass_rate"] == 1.0
        and metrics["identity_pass_rate"] == 1.0
        and metrics["action_safety_pass_rate"] == 1.0
        and metrics["critical_failures"] == 0
    )


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    report = await evaluate(args.cases, settings)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not args.strict or strict_pass(report) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
