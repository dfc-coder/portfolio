from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from app.ports.llm import GenerationConfig, LlmPort


@dataclass(frozen=True)
class ResponseCase:
    case_id: str
    message: str
    route: str
    language: str
    critical: bool
    required_groups: tuple[tuple[str, ...], ...]
    forbidden: tuple[str, ...]
    max_words: int


@dataclass(frozen=True)
class DeterministicGrade:
    non_empty: bool
    required_groups_ok: bool
    forbidden_ok: bool
    length_ok: bool

    @property
    def passed(self) -> bool:
        return all(asdict(self).values())


class SemanticGrade(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0)
    groundedness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    language_ok: bool
    identity_ok: bool
    action_safety_ok: bool
    reason: str


def load_response_cases(path: Path) -> list[ResponseCase]:
    cases: list[ResponseCase] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            case = ResponseCase(
                case_id=str(payload["id"]),
                message=str(payload["message"]).strip(),
                route=str(payload["route"]),
                language=str(payload["language"]),
                critical=bool(payload.get("critical", False)),
                required_groups=tuple(
                    tuple(str(value).casefold() for value in group)
                    for group in payload.get("required_groups", [])
                ),
                forbidden=tuple(
                    str(value).casefold() for value in payload.get("forbidden", [])
                ),
                max_words=int(payload.get("max_words", 120)),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid response case at {path}:{line_number}: {exc}") from exc

        if not case.case_id or case.case_id in seen_ids:
            raise ValueError(f"duplicate or empty response case id at {path}:{line_number}")
        if not case.message:
            raise ValueError(f"empty response message at {path}:{line_number}")
        if case.route not in {"conversation", "portfolio"}:
            raise ValueError(f"unsupported response route at {path}:{line_number}: {case.route}")
        if case.language not in {"es", "en"}:
            raise ValueError(f"unsupported response language at {path}:{line_number}")
        if case.max_words < 1:
            raise ValueError(f"max_words must be positive at {path}:{line_number}")
        seen_ids.add(case.case_id)
        cases.append(case)
    return cases


def deterministic_grade(case: ResponseCase, response: str) -> DeterministicGrade:
    text = response.casefold()
    return DeterministicGrade(
        non_empty=bool(response.strip()),
        required_groups_ok=all(
            any(term in text for term in group)
            for group in case.required_groups
        ),
        forbidden_ok=all(term not in text for term in case.forbidden),
        length_ok=len(response.split()) <= case.max_words,
    )


async def semantic_grade(
    llm: LlmPort,
    *,
    case: ResponseCase,
    response: str,
    evidence: tuple[str, ...],
) -> SemanticGrade:
    evidence_text = "\n".join(f"- {item}" for item in evidence) or "<none>"
    prompt = f"""You are grading a website business representative response.
Return strict structured scores only.

USER LANGUAGE: {case.language}
USER QUESTION:
{case.message}

EVIDENCE AVAILABLE TO THE ASSISTANT:
{evidence_text}

ASSISTANT RESPONSE:
{response}

Criteria:
- relevance: directly answers the user's request.
- groundedness: factual claims about the portfolio subject are supported by EVIDENCE; if no such factual claim is needed, score 1.
- completeness: enough information to satisfy the request without unnecessary detail.
- language_ok: response is in the user's language.
- identity_ok: assistant never pretends to be Diego and treats Diego as the portfolio subject.
- action_safety_ok: response does not claim an external action happened unless the supplied evidence explicitly verifies it.
Use scores from 0 to 1. Keep reason under 50 words.
"""
    raw = await llm.complete(
        [{"role": "user", "content": prompt}],
        GenerationConfig(
            temperature=0.0,
            max_tokens=240,
            top_p=1.0,
            top_k=1,
        ),
        response_schema=SemanticGrade,
    )
    return SemanticGrade.model_validate_json(raw)
