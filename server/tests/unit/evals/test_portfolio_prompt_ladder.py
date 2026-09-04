from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.evals import run_portfolio_prompt_ladder as ladder


@pytest.mark.asyncio
async def test_ladder_runs_v1_through_v4_on_portfolio_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, bool]] = []

    async def fake_evaluate(
        cases: Path,
        settings: Any,
        *,
        portfolio_prompt_version: str,
        portfolio_only: bool,
    ) -> dict[str, Any]:
        del cases, settings
        calls.append((portfolio_prompt_version, portfolio_only))
        score = float(portfolio_prompt_version[-1]) / 4.0
        return {
            "metadata": {"candidate_id": f"portfolio-{portfolio_prompt_version}"},
            "metrics": {
                "hard_contract_pass_rate": 1.0,
                "language_pass_rate": 1.0,
                "identity_pass_rate": 1.0,
                "action_safety_pass_rate": 1.0,
                "critical_hard_contract_failures": 0,
                "relevance": score,
            },
        }

    monkeypatch.setattr(ladder, "evaluate", fake_evaluate)

    output_dir = tmp_path / "reports"
    summary = await ladder.run_ladder(
        Path("cases.jsonl"),
        output_dir,
        object(),  # type: ignore[arg-type]
    )

    assert calls == [("v1", True), ("v2", True), ("v3", True), ("v4", True)]
    assert summary["sequence"] == [
        "portfolio-v1",
        "portfolio-v2",
        "portfolio-v3",
        "portfolio-v4",
    ]
    assert summary["final_hard_contracts_pass"] is True
    assert len(summary["comparisons"]) == 4
    assert (output_dir / "portfolio-v1.json").exists()
    assert (output_dir / "portfolio-v4.json").exists()
    persisted = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert persisted["comparisons"][0]["baseline"] == "portfolio-v1"
    assert persisted["comparisons"][0]["candidate"] == "portfolio-v2"
