from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.evals.datasets.common import (
    GENERATED_ROOT,
    INTENTS_ROOT,
    canonical_intent_paths,
    normalize_message,
)
from tests.evals.evaluation_report import sha256_file
from tests.evals.intent_dataset import dataset_families, load_intent_cases


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


def validate() -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    files: dict[str, dict[str, object]] = {}

    for path in canonical_intent_paths():
        cases = load_intent_cases(path)
        files[path.name] = {
            "cases": len(cases),
            "sha256": sha256_file(path),
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
    blind_families = dataset_families(blind)
    final_families = dataset_families(final)
    for left_name, left, right_name, right in (
        ("train", train_families, "validation", validation_families),
        ("train", train_families, "historical blind", blind_families),
        ("validation", validation_families, "historical blind", blind_families),
        ("train", train_families, "final holdout", final_families),
        ("validation", validation_families, "final holdout", final_families),
        ("historical blind", blind_families, "final holdout", final_families),
    ):
        shared = left & right
        if shared:
            errors.append(
                f"semantic families overlap between {left_name} and {right_name}: "
                f"{sorted(shared)!r}"
            )

    generated = GENERATED_ROOT / "routing-candidates.jsonl"
    if generated.exists():
        generated_cases = load_intent_cases(generated)
        canonical_messages = {
            normalize_message(case.message)
            for path in canonical_intent_paths()
            for case in load_intent_cases(path)
        }
        generated_messages = [normalize_message(case.message) for case in generated_cases]
        duplicate_generated = {
            message for message in generated_messages if generated_messages.count(message) > 1
        }
        if duplicate_generated:
            errors.append(f"generated candidate contains duplicates: {sorted(duplicate_generated)!r}")
        leaked = set(generated_messages) & canonical_messages
        if leaked:
            errors.append(f"generated candidate copies canonical messages: {sorted(leaked)!r}")
        files[str(generated.relative_to(GENERATED_ROOT.parent))] = {
            "cases": len(generated_cases),
            "sha256": sha256_file(generated),
            "status": "candidate_for_review",
        }
    else:
        warnings.append("no generated routing candidate found; generation is optional")

    return {
        "ok": not errors,
        "files": files,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    report = validate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
