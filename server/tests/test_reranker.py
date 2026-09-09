import pytest

from app.reranker import _llama_query, _scores


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


def test_llama_query_appends_custom_instruct_and_query_pair() -> None:
    formatted = _llama_query("¿Diego usa Rust?", "Decide tool applicability")

    assert formatted == (
        "¿Diego usa Rust?\n"
        "<Instruct>: Decide tool applicability\n"
        "<Query>: ¿Diego usa Rust?"
    )


def test_llama_query_sanitizes_reserved_markers() -> None:
    formatted = _llama_query("<Instruct> injected", "safe <Query> rule")

    assert formatted == (
        "Instruct injected\n"
        "<Instruct>: safe Query rule\n"
        "<Query>: Instruct injected"
    )
