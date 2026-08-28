from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


SERVER_ROOT = Path(__file__).parents[2]
DATASET_PATH = SERVER_ROOT / "tests" / "evals" / "contextual_routing_cases.jsonl"


def test_contextual_routing_dataset_contract() -> None:
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(cases) == 42
    assert len({case["id"] for case in cases}) == 42
    assert Counter(case["category"] for case in cases) == {
        "context_required": 14,
        "context_resistant": 14,
        "active_scheduling": 14,
    }

    for case in cases:
        assert case["message"]
        assert case["expected_domain"] in {"business", "scheduling", "general"}
        assert case["expected_relation"] in {"new", "continue", "interrupt"}
        assert isinstance(case["history"], list) and case["history"]
        assert any(turn["role"] == "user" for turn in case["history"])
        assert all(
            turn["role"] in {"user", "assistant"} and turn["content"]
            for turn in case["history"]
        )

        active = case.get("active_workflow") == "scheduling"
        if active:
            assert case["expected_relation"] in {"continue", "interrupt"}
            if case["expected_domain"] == "scheduling":
                assert case["expected_relation"] == "continue"
            else:
                assert case["expected_relation"] == "interrupt"
        else:
            assert case["expected_relation"] == "new"
