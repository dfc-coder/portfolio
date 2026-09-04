from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from tests.evals.datasets.common import (
    EVALS_ROOT,
    GENERATED_ROOT,
    INTENTS_ROOT,
    canonical_intent_paths,
    normalize_message,
)
from tests.evals.evaluation_report import sha256_file
from tests.evals.intent_dataset import dataset_families, load_intent_cases
from tests.evals.responses.grader import load_response_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate evaluation datasets and leakage rules.")
    parser.add_argument(
        "--generated",
        type=Path,
        default=GENERATED_ROOT / "routing-candidates.jsonl",
    )
    return parser.parse_args()


def message_set(path: Path) -> set[str]:
    return {normalize_message(case.message) for case in load_intent_cases(path)}


def overlaps(left: Path, right: Path) -> set[str]:
    return message_set(left) & message_set(right)


def validate(generated: Path | None = None) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    files: dict[str, dict[str, object]] = {}

    for path in canonical_intent_paths():
        cases = load_intent_cases(path)
        files[path.name] = {
            "cases": len(cases),
            "sha256": sha256_file(path),
        }

    response_path = EVALS_ROOT / "responses" / "cases.jsonl"
    response_cases = load_response_cases(response_path)
    response_counts = Counter(normalize_message(case.message) for case in response_cases)
    duplicate_responses = {message for message, count in response_counts.items() if count > 1}
    if duplicate_responses:
        errors.append(f"response dataset contains duplicate messages: {sorted(duplicate_responses)!r}")
    files["responses/cases.jsonl"] = {
        "cases": len(response_cases),
        "sha256": sha256_file(response_path),
    }

    train = INTENTS_ROOT / "train.jsonl"
    train_oos = INTENTS_ROOT / "train_oos.jsonl"
    validation = INTENTS_ROOT / "validation.jsonl"
    challenge = INTENTS_ROOT / "challenge.jsonl"
    blind = INTENTS_ROOT / "blind_test.jsonl"
    final = INTENTS_ROOT / "final_holdout_v2.jsonl"

    tuning_messages = message_set(train) | message_set(train_oos)
    for name, path in (
        ("validation", validation),
        ("historical blind", blind),
        ("final holdout", final),
    ):
        leaked = tuning_messages & message_set(path)
        if leaked:
            errors.append(f"training messages leak into {name}: {sorted(leaked)!r}")

    for name, path in (
        ("train", train),
        ("train_oos", train_oos),
        ("validation", validation),
        ("challenge", challenge),
        ("historical blind", blind),
    ):
        leaked = overlaps(path, final)
        if leaked:
            errors.append(f"{name} messages leak into final holdout: {sorted(leaked)!r}")

    train_families = dataset_families(train) | dataset_families(train_oos)
    validation_families = dataset_families(validation)
    challenge_families = dataset_families(challenge)
    blind_families = dataset_families(blind)
    final_families = dataset_families(final)
    for left_name, left, right_name, right in (
        ("train", train_families, "validation", validation_families),
        ("train", train_families, "historical blind", blind_families),
        ("validation", validation_families, "historical blind", blind_families),
        ("train", train_families, "final holdout", final_families),
        ("validation", validation_families, "final holdout", final_families),
        ("challenge", challenge_families, "final holdout", final_families),
        ("historical blind", blind_families, "final holdout", final_families),
    ):
        shared = left & right
        if shared:
            errors.append(
                f"semantic families overlap between {left_name} and {right_name}: "
                f"{sorted(shared)!r}"
            )

    candidate = generated or GENERATED_ROOT / "routing-candidates.jsonl"
    if candidate.exists():
        generated_cases = load_intent_cases(candidate)
        canonical_messages = {
            normalize_message(case.message)
            for path in canonical_intent_paths()
            for case in load_intent_cases(path)
        }
        counts = Counter(normalize_message(case.message) for case in generated_cases)
        duplicate_generated = {message for message, count in counts.items() if count > 1}
        if duplicate_generated:
            errors.append(f"generated candidate contains duplicates: {sorted(duplicate_generated)!r}")
        leaked = set(counts) & canonical_messages
        if leaked:
            errors.append(f"generated candidate copies canonical messages: {sorted(leaked)!r}")
        files[str(candidate)] = {
            "cases": len(generated_cases),
            "sha256": sha256_file(candidate),
            "status": "candidate_for_review",
        }
    else:
        warnings.append(f"generated candidate not found: {candidate}; generation is optional")

    return {
        "ok": not errors,
        "files": files,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    args = parse_args()
    report = validate(args.generated)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
