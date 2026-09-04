from __future__ import annotations

from pathlib import Path

import pytest

from tests.evals.datasets.common import GENERATED_ROOT, normalize_message
from tests.evals.datasets.generate import ensure_candidate_output
from tests.evals.datasets.validate import validate


def test_message_normalization_is_case_and_whitespace_insensitive() -> None:
    assert normalize_message("  ¿Qué   PODÉS hacer?  ") == "¿qué podés hacer?"


def test_generator_only_writes_below_generated_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="generated datasets may only be written"):
        ensure_candidate_output(tmp_path / "train.jsonl")

    ensure_candidate_output(GENERATED_ROOT / "candidate.jsonl")


def test_canonical_eval_datasets_pass_structural_and_leakage_validation(
    tmp_path: Path,
) -> None:
    report = validate(tmp_path / "missing-generated.jsonl")

    assert report["ok"] is True
    assert report["errors"] == []
