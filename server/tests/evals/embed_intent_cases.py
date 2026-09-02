from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.ports.embeddings import EmbeddingTask
from tests.evals.intent_dataset import load_intent_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed labeled intent cases with the live encoder.")
    parser.add_argument("--cases", type=Path, required=True)
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    cases = load_intent_cases(args.cases)

    async with httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as http:
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=http,
        )
        records = []
        for case in cases:
            vector = await embeddings.embed_query(case.message, EmbeddingTask.ROUTING)
            records.append(
                {
                    "id": case.case_id,
                    "message": case.message,
                    "intent": case.intent.value if case.intent is not None else None,
                    "route": case.route,
                    "language": case.language,
                    "family": case.family,
                    "critical": case.critical,
                    "active_workflow": case.active_workflow,
                    "embedding": vector,
                }
            )

    print(
        json.dumps(
            {
                "embedding_model": settings.embedding_model,
                "records": records,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
