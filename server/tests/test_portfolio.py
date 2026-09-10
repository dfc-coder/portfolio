from types import SimpleNamespace

import pytest

from app.portfolio import Portfolio


class FakeEmbeddings:
    def __init__(self) -> None:
        self.embeddings = self

    async def create(self, *, model: str, input: list[str]):
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[1.0, 0.0])
                for index, _ in enumerate(input)
            ]
        )


@pytest.mark.asyncio
async def test_exact_technology_evidence_is_preferred() -> None:
    portfolio = Portfolio(
        {
            "skills": {"programming_languages": ["Python", "Rust", "Go"]},
            "experience": [
                {"name": "Cloud delivery", "summary": "AWS and CI/CD delivery."},
                {"name": "Backend", "summary": "Python and FastAPI services."},
            ],
        },
        FakeEmbeddings(),
        model="embedding",
        max_documents=1,
    )

    facts = await portfolio.search("Does he have experience with Rust?")

    assert len(facts) == 1
    assert facts[0]["source"] == "skills.programming_languages"
    assert "Rust" in facts[0]["text"]


@pytest.mark.asyncio
async def test_short_technology_name_is_not_dropped() -> None:
    portfolio = Portfolio(
        {
            "skills": {"programming_languages": ["Python", "Rust", "Go"]},
            "languages": [
                {"language": "Español", "level": "Nativo"},
                {"language": "Inglés", "level": "A2"},
            ],
        },
        FakeEmbeddings(),
        model="embedding",
        max_documents=1,
    )

    facts = await portfolio.search("Go programming language")

    assert len(facts) == 1
    assert facts[0]["source"] == "skills.programming_languages"
    assert "Go" in facts[0]["text"]


@pytest.mark.asyncio
async def test_project_name_evidence_is_preferred() -> None:
    portfolio = Portfolio(
        {
            "projects": [
                {
                    "name": "System-G (Growntrol)",
                    "summary": "ESP32 control system with a Rust domain core.",
                }
            ],
            "experience": [
                {"name": "Cloud delivery", "summary": "AWS and CI/CD delivery."}
            ],
        },
        FakeEmbeddings(),
        model="embedding",
        max_documents=1,
    )

    facts = await portfolio.search("System-G Growntrol")

    assert len(facts) == 1
    assert facts[0]["source"] == "projects.0"


def test_profile_dict_sections_are_split_into_small_documents() -> None:
    documents = Portfolio._build_documents(
        {
            "skills": {
                "programming_languages": ["Rust", "Go"],
                "frameworks": ["FastAPI"],
            }
        }
    )

    assert [source for source, _ in documents] == [
        "skills.programming_languages",
        "skills.frameworks",
    ]
