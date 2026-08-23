from __future__ import annotations

import asyncio

from tests.evals import run_family_model_diagnostic as diagnostic

# For Qwen3.5, test only the exact Unsloth-recommended non-thinking
# general-task configuration for the small 0.8B/2B/4B/9B models:
# temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
# presence_penalty=1.5, repetition_penalty=1.0, enable_thinking=false.
#
# No project-current, reasoning, thinking, or minimal-prompt variants are
# included in this benchmark. This keeps the result attributable to the
# documented Unsloth configuration rather than to a parameter search.
diagnostic.QWEN35_PROFILES = tuple(
    profile
    for profile in diagnostic.QWEN35_PROFILES
    if profile.name == "qwen_unsloth_instruct_general"
)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(diagnostic.main()))
