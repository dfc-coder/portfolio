from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from typing import Any

from openai import AsyncOpenAI

Profile = dict[str, Any]
Fact = tuple[str, str]

_QUERY_PREFIX = (
    "Instruct: Given a visitor question about a professional portfolio, retrieve specific portfolio "
    "passages that provide direct evidence needed to answer it.\nQuery: "
)
_RRF_K = 20
_MIN_RANK_WINDOW = 12
_BM25_K1 = 1.2
_BM25_B = 0.75

_STOPWORDS = {
    "a",
    "al",
    "algo",
    "algun",
    "alguna",
    "an",
    "and",
    "are",
    "by",
    "con",
    "de",
    "del",
    "did",
    "do",
    "does",
    "el",
    "en",
    "es",
    "for",
    "from",
    "has",
    "have",
    "her",
    "his",
    "in",
    "is",
    "la",
    "las",
    "le",
    "lo",
    "los",
    "me",
    "mi",
    "of",
    "on",
    "or",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "son",
    "su",
    "sus",
    "the",
    "their",
    "tiene",
    "un",
    "una",
    "what",
    "which",
    "with",
    "without",
    "y",
}

_IDENTITY_TERMS = {"identity", "identidad", "name", "nombre", "quien", "who"}

_SECTION_ALIASES = {
    "education": {
        "degree",
        "education",
        "educacion",
        "estudio",
        "estudios",
        "estudiar",
        "formacion",
        "studied",
        "studies",
        "universidad",
        "university",
    },
    "certifications": {
        "certificate",
        "certificates",
        "certificacion",
        "certificaciones",
        "certification",
        "certifications",
        "credential",
        "credentials",
    },
    "projects": {"project", "projects", "proyecto", "proyectos"},
    "skills": {
        "habilidad",
        "habilidades",
        "skill",
        "skills",
        "stack",
        "tecnologia",
        "tecnologias",
        "technology",
        "technologies",
        "lenguaje",
        "lenguajes",
        "language",
        "languages",
    },
    "professional_experience": {
        "career",
        "company",
        "empresa",
        "experiencia",
        "experience",
        "trabajo",
        "trayectoria",
        "work",
    },
    "services": {"service", "services", "servicio", "servicios"},
}

_SECTION_HINTS = {
    "education": ("education", "program", "institution"),
    "certifications": ("certifications", "certification"),
    "projects": ("projects", "project", "stack"),
    "skills": ("skills", "stack"),
    "professional_experience": ("professional", "experience", "company", "title"),
    "services": ("services", "service"),
}


class Portfolio:
    def __init__(
        self,
        profile: Profile,
        embeddings: AsyncOpenAI,
        *,
        model: str,
        max_chars: int = 4000,
        max_documents: int = 4,
        min_score: float = 0.10,
    ) -> None:
        self._embeddings = embeddings
        self._model = model
        self._max_chars = max_chars
        self._max_documents = max_documents
        self._min_score = min_score
        self._documents = self._build_documents(profile)
        self._vectors: list[list[float]] | None = None

        owner = profile.get("owner")
        owner_name = owner.get("name") if isinstance(owner, dict) else None
        self._subject_terms = self._terms(owner_name) if isinstance(owner_name, str) else set()
        self._programming_languages = self._string_token_sets(
            profile.get("skills", {}).get("programming_languages", [])
            if isinstance(profile.get("skills"), dict)
            else []
        )
        self._project_names = self._project_name_token_sets(profile.get("projects", []))

        self._lexical_documents = [
            Counter(self._tokens(self._search_text(source, text)))
            for source, text in self._documents
        ]
        self._document_frequency: Counter[str] = Counter()
        for terms in self._lexical_documents:
            self._document_frequency.update(terms.keys())
        total_terms = sum(sum(terms.values()) for terms in self._lexical_documents)
        self._avg_document_length = total_terms / max(len(self._lexical_documents), 1)

    async def warm(self) -> None:
        if self._vectors is None:
            self._vectors = await self._embed(
                [self._search_text(source, text) for source, text in self._documents]
            )

    async def search(
        self,
        query: str,
        *,
        user_query: str | None = None,
    ) -> list[dict[str, str]]:
        await self.warm()
        assert self._vectors is not None

        effective_query = self._effective_query(query, user_query)
        query_vector = (await self._embed([f"{_QUERY_PREFIX}{effective_query}"]))[0]
        query_terms = {
            term for term in self._tokens(effective_query) if term not in _STOPWORDS
        }

        semantic_scores = [
            self._cosine(query_vector, vector)
            for vector in self._vectors
        ]
        lexical_scores = [
            self._bm25(query_terms, document_terms)
            for document_terms in self._lexical_documents
        ]
        ranked_indices = self._fused_ranking(semantic_scores, lexical_scores)

        facts: list[dict[str, str]] = []
        chars = 0
        for index in ranked_indices:
            if len(facts) >= self._max_documents:
                break

            semantic_score = semantic_scores[index]
            lexical_score = lexical_scores[index]
            if lexical_score <= 0 and semantic_score < self._min_score:
                continue

            source, text = self._documents[index]
            if facts and chars + len(text) > self._max_chars:
                continue
            facts.append({"source": source, "text": text})
            chars += len(text)

        return facts

    def _effective_query(self, tool_query: str, user_query: str | None) -> str:
        raw_parts = [part for part in (user_query, tool_query) if part and part.strip()]
        raw_tokens = [token for part in raw_parts for token in self._tokens(part)]
        identity_query = bool(set(raw_tokens) & _IDENTITY_TERMS)

        tokens: list[str] = []
        seen: set[str] = set()
        for token in raw_tokens:
            if token in _STOPWORDS:
                continue
            if not identity_query and token in self._subject_terms:
                continue
            if token not in seen:
                seen.add(token)
                tokens.append(token)

        query_terms = set(tokens)
        hints = self._query_hints(query_terms)
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                tokens.append(hint)

        if tokens:
            return " ".join(tokens)
        return tool_query.strip() or (user_query or "").strip()

    def _query_hints(self, query_terms: set[str]) -> list[str]:
        hints: list[str] = []
        matched_sections: list[str] = []

        language_query = any(
            language_terms and language_terms <= query_terms
            for language_terms in self._programming_languages
        )
        project_query = any(
            any(term in query_terms for term in project_terms if len(term) >= 4)
            for project_terms in self._project_names
        )

        if language_query:
            matched_sections.extend(("projects", "skills"))
        elif query_terms & _SECTION_ALIASES["professional_experience"]:
            matched_sections.append("professional_experience")

        if project_query or query_terms & _SECTION_ALIASES["projects"]:
            matched_sections.append("projects")

        for section in ("education", "certifications", "skills", "services"):
            if query_terms & _SECTION_ALIASES[section]:
                matched_sections.append(section)

        for section in matched_sections:
            for hint in _SECTION_HINTS[section]:
                if hint not in hints:
                    hints.append(hint)
        return hints

    def _bm25(self, query_terms: set[str], document_terms: Counter[str]) -> float:
        if not query_terms or not document_terms or not self._documents:
            return 0.0

        document_length = sum(document_terms.values())
        average_length = self._avg_document_length or 1.0
        document_count = len(self._documents)
        score = 0.0

        for term in query_terms:
            frequency = document_terms.get(term, 0)
            if frequency <= 0:
                continue

            document_frequency = self._document_frequency.get(term, 0)
            idf = math.log(
                1.0
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            normalization = frequency + _BM25_K1 * (
                1.0 - _BM25_B + _BM25_B * document_length / average_length
            )
            score += idf * (frequency * (_BM25_K1 + 1.0)) / normalization

        return score

    def _fused_ranking(
        self,
        semantic_scores: list[float],
        lexical_scores: list[float],
    ) -> list[int]:
        if not semantic_scores:
            return []

        window = min(
            len(semantic_scores),
            max(_MIN_RANK_WINDOW, self._max_documents * 4),
        )
        semantic_order = sorted(
            range(len(semantic_scores)),
            key=lambda index: semantic_scores[index],
            reverse=True,
        )[:window]
        lexical_order = [
            index
            for index in sorted(
                range(len(lexical_scores)),
                key=lambda index: lexical_scores[index],
                reverse=True,
            )
            if lexical_scores[index] > 0
        ][:window]

        semantic_rank = {index: rank for rank, index in enumerate(semantic_order, start=1)}
        lexical_rank = {index: rank for rank, index in enumerate(lexical_order, start=1)}
        candidates = set(semantic_order) | set(lexical_order)

        def rrf_score(index: int) -> float:
            score = 0.0
            if index in semantic_rank:
                score += 1.0 / (_RRF_K + semantic_rank[index])
            if index in lexical_rank:
                score += 1.0 / (_RRF_K + lexical_rank[index])
            return score

        return sorted(
            candidates,
            key=lambda index: (
                rrf_score(index),
                lexical_scores[index],
                semantic_scores[index],
            ),
            reverse=True,
        )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._embeddings.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    @staticmethod
    def _build_documents(profile: Profile) -> list[Fact]:
        documents: list[Fact] = []
        for section, value in profile.items():
            if isinstance(value, list):
                documents.extend(
                    (f"{section}.{index}", json.dumps(item, ensure_ascii=False))
                    for index, item in enumerate(value)
                )
                continue

            if isinstance(value, dict):
                documents.extend(
                    (f"{section}.{key}", json.dumps(item, ensure_ascii=False))
                    for key, item in value.items()
                )
                continue

            documents.append((section, json.dumps(value, ensure_ascii=False)))
        return documents

    @staticmethod
    def _search_text(source: str, text: str) -> str:
        label = re.sub(r"[._]+", " ", source)
        return f"{label}\n{text}"

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", text.casefold())
            if unicodedata.category(character) != "Mn"
        )
        return [
            term
            for term in re.findall(r"[\w.+#-]+", normalized)
            if len(term) >= 2
        ]

    @classmethod
    def _terms(cls, text: str) -> set[str]:
        return set(cls._tokens(text))

    @classmethod
    def _string_token_sets(cls, values: Any) -> tuple[set[str], ...]:
        if not isinstance(values, list):
            return ()
        return tuple(
            cls._terms(value)
            for value in values
            if isinstance(value, str) and value.strip()
        )

    @classmethod
    def _project_name_token_sets(cls, projects: Any) -> tuple[set[str], ...]:
        if not isinstance(projects, list):
            return ()
        return tuple(
            cls._terms(name)
            for project in projects
            if isinstance(project, dict)
            and isinstance((name := project.get("name")), str)
            and name.strip()
        )

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
