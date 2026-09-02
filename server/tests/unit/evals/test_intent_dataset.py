from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.domain.routing import Intent
from tests.evals.intent_dataset import dataset_families, load_intent_cases


ROOT = Path("tests/evals/intents")


def test_intent_splits_exist_and_are_non_empty() -> None:
    for name in (
        "train.jsonl",
        "train_oos.jsonl",
        "validation.jsonl",
        "blind_test.jsonl",
        "challenge.jsonl",
        "final_holdout_v2.jsonl",
    ):
        path = ROOT / name
        assert path.exists()
        assert load_intent_cases(path)


def test_tuning_and_final_families_do_not_leak() -> None:
    train = dataset_families(ROOT / "train.jsonl") | dataset_families(ROOT / "train_oos.jsonl")
    validation = dataset_families(ROOT / "validation.jsonl")
    final_holdout = dataset_families(ROOT / "final_holdout_v2.jsonl")

    assert train.isdisjoint(validation)
    assert train.isdisjoint(final_holdout)
    assert validation.isdisjoint(final_holdout)


def test_train_contains_balanced_spanish_and_english_examples_per_intent() -> None:
    cases = load_intent_cases(ROOT / "train.jsonl")
    counts = Counter((case.intent, case.language) for case in cases)

    for intent in Intent:
        assert counts[(intent, "es")] >= 6
        assert counts[(intent, "en")] >= 6


def test_main_training_set_contains_no_oos_label() -> None:
    cases = load_intent_cases(ROOT / "train.jsonl")

    assert all(not case.out_of_scope for case in cases)


def test_explicit_oos_training_set_contains_only_oos() -> None:
    cases = load_intent_cases(ROOT / "train_oos.jsonl")

    assert len(cases) >= 12
    assert all(case.out_of_scope for case in cases)
    counts = Counter(case.language for case in cases)
    assert counts["es"] >= 6
    assert counts["en"] >= 6


def test_validation_historical_blind_and_final_holdout_contain_oos() -> None:
    validation = load_intent_cases(ROOT / "validation.jsonl")
    blind = load_intent_cases(ROOT / "blind_test.jsonl")
    final_holdout = load_intent_cases(ROOT / "final_holdout_v2.jsonl")

    assert sum(case.out_of_scope for case in validation) >= 4
    assert sum(case.out_of_scope for case in blind) >= 4
    assert sum(case.out_of_scope for case in final_holdout) >= 10


def test_final_holdout_messages_are_not_in_any_tuning_or_historical_split() -> None:
    prior_names = (
        "train.jsonl",
        "train_oos.jsonl",
        "validation.jsonl",
        "challenge.jsonl",
        "blind_test.jsonl",
    )
    prior_messages = {
        case.message.casefold()
        for name in prior_names
        for case in load_intent_cases(ROOT / name)
    }
    final_messages = {
        case.message.casefold()
        for case in load_intent_cases(ROOT / "final_holdout_v2.jsonl")
    }

    assert prior_messages.isdisjoint(final_messages)


def test_challenge_preserves_the_seventy_routing_cases() -> None:
    cases = load_intent_cases(ROOT / "challenge.jsonl")

    assert len(cases) == 70
