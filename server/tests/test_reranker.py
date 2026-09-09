import pytest

from app.reranker import _scores


def test_scores_restore_document_order() -> None:
    payload = {
        "results": [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.2},
            {"index": 1, "relevance_score": 0.5},
        ]
    }

    assert _scores(payload, 3) == [0.2, 0.5, 0.9]


def test_scores_require_every_document() -> None:
    with pytest.raises(ValueError, match="every document"):
        _scores({"results": [{"index": 0, "relevance_score": 0.9}]}, 2)


def test_scores_reject_duplicate_indexes() -> None:
    with pytest.raises(ValueError, match="duplicate index"):
        _scores(
            {
                "results": [
                    {"index": 0, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.8},
                ]
            },
            2,
        )
