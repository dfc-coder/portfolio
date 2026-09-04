from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Config:
    profile_path: Path
    llama_base_url: str
    llama_model: str
    llama_timeout_seconds: float
    embedding_base_url: str
    embedding_model: str
    embedding_timeout_seconds: float
    allowed_origins: tuple[str, ...]
    generation_temperature: float
    generation_max_tokens: int
    context_max_chars: int
    context_max_documents: int
    portfolio_min_score: float

    @classmethod
    def from_env(cls) -> "Config":
        root = Path(__file__).resolve().parents[1]
        return cls(
            profile_path=Path(
                os.getenv("BUSINESS_PROFILE_PATH", root / "config" / "business-profile.json")
            ),
            llama_base_url=os.getenv("LLAMA_BASE_URL", "http://llama:8080").rstrip("/"),
            llama_model=os.getenv("LLAMA_MODEL", "Qwen3.5-2B"),
            llama_timeout_seconds=float(os.getenv("LLAMA_TIMEOUT_SECONDS", "90")),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "http://embedding:8081").rstrip("/"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-0.6B"),
            embedding_timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30")),
            allowed_origins=_csv(
                os.getenv(
                    "ALLOWED_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173",
                )
            ),
            generation_temperature=float(os.getenv("GENERATION_TEMPERATURE", "0.65")),
            generation_max_tokens=int(os.getenv("GENERATION_MAX_TOKENS", "180")),
            context_max_chars=int(os.getenv("CONTEXT_MAX_CHARS", "4000")),
            context_max_documents=int(os.getenv("CONTEXT_MAX_DOCUMENTS", "4")),
            portfolio_min_score=float(os.getenv("PORTFOLIO_MIN_SCORE", "0.10")),
        )
