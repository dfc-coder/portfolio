from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterator


def _rows(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if {"testIdx", "promptIdx", "gradingResult"}.issubset(node):
            yield node
            return
        for value in node.values():
            yield from _rows(value)
    elif isinstance(node, list):
        for value in node:
            yield from _rows(value)


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: report_eval_cache.py <promptfoo-output.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Judge prompt cache: no eval output at {path}")
        return 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Judge prompt cache: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    input_tokens = 0
    cached_tokens = 0
    cache_write_tokens = 0
    graded_rows = 0

    for row in _rows(payload):
        grading = row.get("gradingResult")
        if not isinstance(grading, dict):
            continue
        usage = grading.get("tokensUsed")
        if not isinstance(usage, dict):
            continue
        details = usage.get("completionDetails")
        if not isinstance(details, dict):
            details = {}

        graded_rows += 1
        input_tokens += _as_int(usage.get("prompt"))
        cached_tokens += _as_int(details.get("cacheReadInputTokens"))
        cache_write_tokens += _as_int(details.get("cacheCreationInputTokens"))

    if graded_rows == 0:
        print("Judge prompt cache: no model-graded token usage found in eval output.")
        return 0

    ratio = cached_tokens / input_tokens if input_tokens else 0.0
    print(
        "Judge prompt cache: "
        f"rows={graded_rows}, input={input_tokens}, cached={cached_tokens}, "
        f"written={cache_write_tokens}, hit_ratio={ratio:.1%}"
    )
    if cached_tokens == 0:
        print(
            "Judge prompt cache note: no cache reads were reported. GPT-5.6 requires "
            "an eligible shared prefix of at least 1024 visible input tokens; do not pad "
            "grader prompts only to force a cache hit."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
