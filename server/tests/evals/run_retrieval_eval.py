from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.agent.context import ProfileDocumentIndex, ProfileRetriever, RetrievedDocument
from app.infrastructure.config.profile_loader import load_business_profile
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    query: str
    answerable: bool
    expected: tuple[str, ...]


@dataclass(frozen=True)
class CaseResult:
    case: RetrievalCase
    top1_id: str
    top1_score: float
    correct_at_1: bool
    correct_at_4: bool
    relevant_score: float | None


@dataclass(frozen=True)
class GateResult:
    threshold: float
    false_accepts: int
    false_rejects: int

    @property
    def viable(self) -> bool:
        return self.false_accepts == 0 and self.false_rejects == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate profile retrieval and whether a fixed cosine relevance gate is viable."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("retrieval_cases.jsonl"),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_cases(path: Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    seen_ids: set[str] = set()

    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            payload: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc

        case_id = payload.get("id")
        query = payload.get("query")
        answerable = payload.get("answerable")
        expected = payload.get("expected", [])

        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"Case at {path}:{line_number} requires a non-empty id")
        if case_id in seen_ids:
            raise ValueError(f"Duplicate case id: {case_id}")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Case {case_id} requires a non-empty query")
        if not isinstance(answerable, bool):
            raise ValueError(f"Case {case_id} requires boolean answerable")
        if not isinstance(expected, list) or not all(
            isinstance(item, str) and item for item in expected
        ):
            raise ValueError(f"Case {case_id} has invalid expected document ids")
        if answerable and not expected:
            raise ValueError(f"Answerable case {case_id} requires expected document ids")
        if not answerable and expected:
            raise ValueError(f"Unanswerable case {case_id} must not define expected documents")

        seen_ids.add(case_id)
        cases.append(
            RetrievalCase(
                case_id=case_id,
                query=query.strip(),
                answerable=answerable,
                expected=tuple(expected),
            )
        )

    if not cases:
        raise ValueError(f"No retrieval cases found in {path}")
    return cases


def validate_expected_documents(
    cases: list[RetrievalCase],
    index: ProfileDocumentIndex,
) -> None:
    document_ids = {document.document_id for document in index.documents}
    for case in cases:
        unknown = sorted(set(case.expected) - document_ids)
        if unknown:
            raise ValueError(
                f"Case {case.case_id} references unknown profile documents: {unknown}"
            )


def find_best_fixed_gate(results: list[CaseResult]) -> GateResult:
    positive_scores = [
        result.relevant_score
        for result in results
        if result.case.answerable and result.relevant_score is not None
    ]
    negative_scores = [
        result.top1_score for result in results if not result.case.answerable
    ]
    if not positive_scores or not negative_scores:
        raise ValueError("Gate evaluation requires answerable and unanswerable cases")

    observed = sorted(set([*positive_scores, *negative_scores]))
    candidates = [observed[0] - 1e-6]
    candidates.extend(
        (left + right) / 2
        for left, right in zip(observed, observed[1:], strict=False)
    )
    candidates.append(observed[-1] + 1e-6)

    evaluated: list[GateResult] = []
    for threshold in candidates:
        false_rejects = sum(score < threshold for score in positive_scores)
        false_accepts = sum(score >= threshold for score in negative_scores)
        evaluated.append(
            GateResult(
                threshold=threshold,
                false_accepts=false_accepts,
                false_rejects=false_rejects,
            )
        )

    return min(
        evaluated,
        key=lambda result: (
            result.false_accepts + result.false_rejects,
            result.false_rejects,
            result.false_accepts,
            result.threshold,
        ),
    )


def evaluate_case(
    case: RetrievalCase,
    ranked: tuple[RetrievedDocument, ...],
) -> CaseResult:
    if not ranked:
        raise ValueError(f"Retriever returned no documents for case {case.case_id}")

    expected = set(case.expected)
    top1 = ranked[0]
    correct_at_1 = case.answerable and top1.document.document_id in expected
    correct_at_4 = case.answerable and any(
        item.document.document_id in expected for item in ranked[:4]
    )

    relevant_score: float | None = None
    if case.answerable:
        matching_scores = [
            item.score for item in ranked if item.document.document_id in expected
        ]
        if not matching_scores:
            raise ValueError(
                f"Expected documents were not ranked for case {case.case_id}"
            )
        relevant_score = max(matching_scores)

    return CaseResult(
        case=case,
        top1_id=top1.document.document_id,
        top1_score=top1.score,
        correct_at_1=correct_at_1,
        correct_at_4=correct_at_4,
        relevant_score=relevant_score,
    )


def print_report(results: list[CaseResult], gate: GateResult, *, verbose: bool) -> None:
    answerable = [result for result in results if result.case.answerable]
    unanswerable = [result for result in results if not result.case.answerable]
    relevant_scores = [
        result.relevant_score
        for result in answerable
        if result.relevant_score is not None
    ]
    negative_scores = [result.top1_score for result in unanswerable]

    print("RETRIEVAL EVAL")
    print(
        f"Cases: {len(results)} "
        f"({len(answerable)} answerable / {len(unanswerable)} unanswerable)"
    )

    print("\nANSWERABLE")
    print(f"correct@1: {sum(result.correct_at_1 for result in answerable)}/{len(answerable)}")
    print(f"correct@4: {sum(result.correct_at_4 for result in answerable)}/{len(answerable)}")
    print(
        "relevant score range: "
        f"{min(relevant_scores):.6f} - {max(relevant_scores):.6f}"
    )

    print("\nUNANSWERABLE")
    print(
        "top1 score range: "
        f"{min(negative_scores):.6f} - {max(negative_scores):.6f}"
    )

    print("\nFIXED COSINE GATE CHECK")
    print(f"best candidate threshold: {gate.threshold:.6f}")
    print(f"false accepts: {gate.false_accepts}/{len(unanswerable)}")
    print(f"false rejects: {gate.false_rejects}/{len(answerable)}")
    if gate.viable:
        print("RESULT: VIABLE on this dataset")
    else:
        print("RESULT: NOT VIABLE")
        print("RECOMMENDATION: do not add a fixed cosine relevance gate")

    false_rejects = [
        result
        for result in answerable
        if result.relevant_score is not None and result.relevant_score < gate.threshold
    ]
    false_accepts = [
        result for result in unanswerable if result.top1_score >= gate.threshold
    ]
    misses_at_4 = [result for result in answerable if not result.correct_at_4]

    if false_rejects:
        print("\nFALSE REJECTS")
        for result in false_rejects:
            assert result.relevant_score is not None
            print(
                f"- {result.case.case_id}: score={result.relevant_score:.6f} "
                f"query={result.case.query}"
            )

    if false_accepts:
        print("\nFALSE ACCEPTS")
        for result in false_accepts:
            print(
                f"- {result.case.case_id}: top1={result.top1_id} "
                f"score={result.top1_score:.6f} query={result.case.query}"
            )

    if misses_at_4:
        print("\nRETRIEVAL MISSES @4")
        for result in misses_at_4:
            print(
                f"- {result.case.case_id}: top1={result.top1_id} "
                f"query={result.case.query}"
            )

    if verbose:
        print("\nALL CASES")
        for result in results:
            label = "answerable" if result.case.answerable else "unanswerable"
            relevant = (
                f" relevant={result.relevant_score:.6f}"
                if result.relevant_score is not None
                else ""
            )
            print(
                f"- {result.case.case_id} [{label}] top1={result.top1_id} "
                f"score={result.top1_score:.6f}{relevant}"
            )


async def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases)
    settings = Settings.from_env()
    profile = load_business_profile(settings.profile_path)
    index = ProfileDocumentIndex(profile)
    validate_expected_documents(cases, index)

    max_chars = sum(len(document.text) for document in index.documents) + 1
    async with httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as http:
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=http,
        )
        retriever = ProfileRetriever(
            index,
            embeddings,
            max_chars=max_chars,
            max_documents=len(index.documents),
        )
        await retriever.warm()

        results = [
            evaluate_case(case, await retriever.search(case.query))
            for case in cases
        ]

    gate = find_best_fixed_gate(results)
    print_report(results, gate, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
