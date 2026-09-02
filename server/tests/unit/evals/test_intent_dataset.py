from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.domain.routing import Intent
from tests.evals.intent_dataset import dataset_families, load_intent_cases


ROOT = Path("tests/evals/intents")


def test_intent_splits_exist_and_are_non_empty() -> None:
    for name in ("train.jsonl", "validation.jsonl", "blind_test.jsonl", "challenge.jsonl"):
        path = ROOT / name
        assert path.exists()
        assert load_intent_cases(path)


def test_train_validation_and_blind_families_do_not_leak() -> None:
    train = dataset_families(ROOT / "train.jsonl")
    validation = dataset_families(ROOT / "validation.jsonl")
    blind = dataset_families(ROOT / "blind_test.jsonl")

    assert train.isdisjoint(validation)
    assert train.isdisjoint(blind)
    assert validation.isdisjoint(blind)


def test_train_contains_balanced_spanish_and_english_examples_per_intent() -> None:
    cases = load_intent_cases(ROOT / "train.jsonl")
    counts = Counter((case.intent, case.language) for case in cases)

    for intent in Intent:
        assert counts[(intent, "es")] >= 6
        assert counts[(intent, "en")] >= 6


def test_blind_cases_are_not_exact_training_messages() -> None:
    train_messages = {
        case.message.casefold()
        for case in load_intent_cases(ROOT / "train.jsonl")
    }
    blind_messages = {
        case.message.casefold()
        for case in load_intent_cases(ROOT / "blind_test.jsonl")
    }

    assert train_messages.isdisjoint(blind_messages)


def test_challenge_preserves_the_seventy_routing_cases() -> None:
    cases = load_intent_cases(ROOT / "challenge.jsonl")

    assert len(cases) == 70
