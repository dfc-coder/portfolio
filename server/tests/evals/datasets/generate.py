from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.llama_cpp import LlamaCppClient
from app.ports.llm import GenerationConfig
from tests.evals.datasets.common import GENERATED_ROOT, known_messages, normalize_message
from tests.evals.intent_dataset import load_intent_cases


class FamilySpec(BaseModel):
    name: str
    intent: str | None
    route: str | None
    critical: bool = False
    description: str


class DatasetSpec(BaseModel):
    name: str
    languages: list[str]
    examples_per_language: int = Field(ge=1, le=20)
    families: list[FamilySpec]


class GeneratedBatch(BaseModel):
    messages: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic routing dataset candidates.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_spec(path: Path) -> DatasetSpec:
    return DatasetSpec.model_validate_json(path.read_text(encoding="utf-8"))


def ensure_candidate_output(path: Path) -> None:
    generated_root = GENERATED_ROOT.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(generated_root):
        raise ValueError(
            f"generated datasets may only be written below {generated_root}; got {resolved}"
        )


async def generate_batch(
    llm: LlamaCppClient,
    *,
    spec: DatasetSpec,
    family: FamilySpec,
    language: str,
) -> list[str]:
    prompt = (
        "Generate evaluation inputs for a business representative.\n"
        "Return only distinct visitor messages. Do not include labels, explanations or answers.\n"
        "Do not copy obvious benchmark phrases; vary wording, tone and sentence structure.\n"
        f"Language: {language}\n"
        f"Semantic family: {family.name}\n"
        f"Behavior: {family.description}\n"
        f"Generate exactly {spec.examples_per_language} messages."
    )
    config = GenerationConfig(
        temperature=0.7,
        max_tokens=700,
        top_p=0.9,
        top_k=20,
    )
    raw = await llm.complete(
        [{"role": "user", "content": prompt}],
        config,
        response_schema=GeneratedBatch,
    )
    batch = GeneratedBatch.model_validate_json(raw)
    messages = [message.strip() for message in batch.messages if message.strip()]
    if len(messages) != spec.examples_per_language:
        raise ValueError(
            f"generator returned {len(messages)} messages for {family.name}/{language}; "
            f"expected {spec.examples_per_language}"
        )
    return messages


async def main() -> int:
    args = parse_args()
    ensure_candidate_output(args.output)
    spec = load_spec(args.spec)
    if not spec.families:
        raise ValueError("dataset spec requires at least one family")
    if any(language not in {"es", "en"} for language in spec.languages):
        raise ValueError("dataset generation currently supports only es and en")

    settings = Settings.from_env()
    existing = known_messages()
    generated: set[str] = set()
    records: list[dict[str, object]] = []

    async with httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as http:
        llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=http,
        )
        for family in spec.families:
            if (family.intent is None) != (family.route is None):
                raise ValueError(
                    f"family {family.name!r} must set both intent and route or neither"
                )
            for language in spec.languages:
                messages = await generate_batch(
                    llm,
                    spec=spec,
                    family=family,
                    language=language,
                )
                for index, message in enumerate(messages, start=1):
                    normalized = normalize_message(message)
                    if normalized in existing or normalized in generated:
                        raise ValueError(
                            f"generated duplicate/leakage for {family.name}/{language}: {message!r}"
                        )
                    generated.add(normalized)
                    records.append(
                        {
                            "id": f"gen-{family.name}-{language}-{index:02d}",
                            "message": message,
                            "intent": family.intent,
                            "route": family.route,
                            "language": language,
                            "family": f"generated-{family.name}",
                            "critical": family.critical,
                        }
                    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )

    # Reuse the canonical parser as the final structural validation step.
    load_intent_cases(args.output)
    print(
        json.dumps(
            {
                "spec": spec.name,
                "output": str(args.output),
                "cases": len(records),
                "model": settings.llama_model,
                "status": "candidate_for_review",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
