from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_portfolio_knowledge_is_not_duplicated_as_intent_utterance_lists() -> None:
    server = ROOT / "server"

    assert not (server / "app" / "agent" / "router.py").exists()
    assert not (
        server
        / "app"
        / "infrastructure"
        / "embeddings"
        / "semantic_router.py"
    ).exists()

    pyproject = (server / "pyproject.toml").read_text(encoding="utf-8")
    assert "semantic-router" not in pyproject

    knowledge = (
        server / "app" / "agent" / "knowledge.py"
    ).read_text(encoding="utf-8")
    assert "ProfileDocumentIndex" in knowledge
    assert "min_score" in knowledge
    assert "_BUSINESS_UTTERANCES" not in knowledge
