from __future__ import annotations

import re
from pathlib import Path

from tests.evals.intent_dataset import load_intent_cases

EVALS_ROOT = Path(__file__).resolve().parents[1]
INTENTS_ROOT = EVALS_ROOT / "intents"
GENERATED_ROOT = EVALS_ROOT / "generated"

CANONICAL_INTENT_FILES = (
    "train.jsonl",
    "train_oos.jsonl",
    "validation.jsonl",
    "challenge.jsonl",
    "blind_test.jsonl",
    "final_holdout_v2.jsonl",
)

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_message(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().casefold())


def canonical_intent_paths() -> tuple[Path, ...]:
    return tuple(INTENTS_ROOT / name for name in CANONICAL_INTENT_FILES)


def known_messages(paths: tuple[Path, ...] | None = None) -> set[str]:
    selected = paths or canonical_intent_paths()
    return {
        normalize_message(case.message)
        for path in selected
        for case in load_intent_cases(path)
    }
