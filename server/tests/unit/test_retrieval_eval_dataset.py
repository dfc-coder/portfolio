from __future__ import annotations

import json
from pathlib import Path

from app.agent.context import ProfileDocumentIndex
from app.infrastructure.config.profile_loader import load_business_profile


SERVER_ROOT = Path(__file__).parents[2]
DATASET_PATH = SERVER_ROOT / "tests" / "evals" / "retrieval_cases.jsonl"
PROFILE_PATH = SERVER_ROOT / "config" / "business-profile.json"


def test_retrieval_dataset_matches_profile_index() -> None:
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(cases) == 40
    assert sum(case["answerable"] for case in cases) == 20
    assert sum(not case["answerable"] for case in cases) == 20
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["query"] for case in cases}) == len(cases)

    profile = load_business_profile(PROFILE_PATH)
    known_document_ids = {
        document.document_id for document in ProfileDocumentIndex(profile).documents
    }

    for case in cases:
        assert case["id"]
        assert case["query"]
        assert isinstance(case["answerable"], bool)

        if case["answerable"]:
            expected = case.get("expected")
            assert isinstance(expected, list) and expected
            assert set(expected) <= known_document_ids
        else:
            assert "expected" not in case
