from types import SimpleNamespace

import pytest

from app.portfolio import Portfolio


class FakeEmbeddings:
    def __init__(self) -> None:
        self.embeddings = self
        self.inputs: list[list[str]] = []

    async def create(self, *, model: str, input: list[str]):
        self.inputs.append(input)
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
            "owner": {"name": "Diego Fernando Cano"},
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

    facts = await portfolio.search("¿Diego tiene experiencia con Rust?")

    assert len(facts) == 1
    assert facts[0]["source"] == "skills.programming_languages"
    assert "Rust" in facts[0]["text"]


@pytest.mark.asyncio
async def test_original_message_is_used_for_semantic_query() -> None:
    embeddings = FakeEmbeddings()
    portfolio = Portfolio(
        {"skills": {"programming_languages": ["Go"]}},
        embeddings,
        model="embedding",
    )
    message = "¿Diego usa Go?"

    await portfolio.search(message)

    assert embeddings.inputs[-1] == [
        "Instruct: Given a visitor question about a professional portfolio, retrieve specific portfolio "
        "passages that provide direct evidence needed to answer it.\nQuery: ¿Diego usa Go?"
    ]


@pytest.mark.asyncio
async def test_subject_name_does_not_displace_exact_technology() -> None:
    portfolio = Portfolio(
        {
            "owner": {"name": "Diego Fernando Cano"},
            "skills": {"programming_languages": ["Python", "Rust", "Go"]},
        },
        FakeEmbeddings(),
        model="embedding",
        max_documents=1,
    )

    facts = await portfolio.search("¿Diego usa Go?")

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
