from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def _assert_no_python_sources(path: Path) -> None:
    if not path.exists():
        return
    assert not list(path.rglob("*.py"))


def test_portfolio_agent_is_knowledge_only() -> None:
    server = ROOT / "server"

    assert not (server / "app" / "agent" / "router.py").exists()
    assert not (server / "app" / "agent" / "scheduler.py").exists()
    _assert_no_python_sources(server / "app" / "scheduling")
    _assert_no_python_sources(server / "app" / "infrastructure" / "calendar")
    assert not (server / "app" / "ports" / "calendar.py").exists()

    pyproject = (server / "pyproject.toml").read_text(encoding="utf-8")
    assert "semantic-router" not in pyproject

    knowledge = (server / "app" / "agent" / "knowledge.py").read_text(encoding="utf-8")
    assert "ProfileDocumentIndex" in knowledge
    assert "min_score" in knowledge
    assert "_BUSINESS_UTTERANCES" not in knowledge
