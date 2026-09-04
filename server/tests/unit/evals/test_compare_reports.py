from __future__ import annotations

from tests.evals.compare_reports import compare


def test_compare_reports_returns_shared_metric_deltas() -> None:
    baseline = {
        "metadata": {"candidate_id": "portfolio-v1"},
        "metrics": {"relevance": 0.8, "groundedness": 0.9, "label": "x"},
    }
    candidate = {
        "metadata": {"candidate_id": "portfolio-v2"},
        "metrics": {"relevance": 0.9, "groundedness": 0.85, "other": 1.0},
    }

    result = compare(baseline, candidate)

    assert result["baseline"] == "portfolio-v1"
    assert result["candidate"] == "portfolio-v2"
    assert result["metrics"]["relevance"]["delta"] == 0.1
    assert result["metrics"]["groundedness"]["delta"] == -0.05
    assert "other" not in result["metrics"]
