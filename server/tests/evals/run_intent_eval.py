from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.agent.router import SupervisedRouteRouter
from app.domain.conversation import ActiveWorkflow, SessionState
from app.infrastructure.business_route_classifier import (
    BusinessRouteClassifier,
    load_route_model,
)
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from tests.evals.intent_dataset import load_intent_cases
from tests.evals.intent_metrics import meets_dod, summarize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate supervised business-route routing.")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


async def evaluate(
    cases_path: Path,
    model_path: Path,
    settings: Settings,
) -> dict[str, Any]:
    cases = load_intent_cases(cases_path)
    model = load_route_model(model_path)
    if model.embedding_model != settings.embedding_model:
        raise ValueError(
            "route artifact embedding model mismatch: "
            f"artifact={model.embedding_model}, runtime={settings.embedding_model}"
        )

    async with httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as http:
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=http,
        )
        router = SupervisedRouteRouter(embeddings, BusinessRouteClassifier(model))
        records: list[dict[str, Any]] = []

        for case in cases:
            state = SessionState(session_id=f"route-eval-{case.case_id}")
            if case.active_workflow == "scheduling":
                state.active_workflow = ActiveWorkflow.SCHEDULING

            started = time.perf_counter()
            decision = await router.route(state, case.message)
            latency_ms = (time.perf_counter() - started) * 1000
            records.append(
                {
                    "case_id": case.case_id,
                    "message": case.message,
                    "language": case.language,
                    "family": case.family,
                    "critical": case.critical,
                    "active_workflow": case.active_workflow,
                    "expected_intent": (
                        case.intent.value if case.intent is not None else None
                    ),
                    "predicted_intent": (
                        decision.intent.value if decision.intent is not None else None
                    ),
                    "expected_route": case.route,
                    "predicted_route": (
                        decision.domain.value if decision.domain is not None else None
                    ),
                    "accepted": decision.accepted,
                    "confidence": round(decision.confidence, 6),
                    "margin": round(decision.margin, 6),
                    "source": decision.source,
                    "scores": decision.scores,
                    "latency_ms": round(latency_ms, 2),
                }
            )

    metrics = summarize(records)
    metrics["dataset"] = str(cases_path)
    metrics["model"] = {
        "version": model.version,
        "embedding_model": model.embedding_model,
        "embedding_dimension": model.embedding_dimension,
        "routes": [route.value for route in model.routes],
        "min_confidence": model.min_confidence,
        "min_margin": model.min_margin,
        "training_dataset_hash": model.training_dataset_hash,
        "seed": model.seed,
    }
    return metrics


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    report = await evaluate(args.cases, args.model, settings)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if meets_dod(report) or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
