import pytest

from app.search import PortfolioSearch


class FakeEmbeddings:
    async def documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "Rust" in text else [0.0, 1.0] for text in texts]

    async def query(self, text: str) -> list[float]:
        return [1.0, 0.0]


@pytest.mark.asyncio
async def test_search_returns_relevant_profile_fact() -> None:
    profile = {
        "owner": {"name": "Diego"},
        "projects": [{"name": "PocketTrace", "stack": ["Rust"]}],
    }
    search = PortfolioSearch(profile, FakeEmbeddings(), min_score=0.5)

    facts = await search.search("¿Trabajó con Rust?")

    assert len(facts) == 1
    assert facts[0].source == "projects.0"
    assert "Rust" in facts[0].text
