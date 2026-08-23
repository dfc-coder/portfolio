from __future__ import annotations

import asyncio

from tests.evals import run_family_model_diagnostic as diagnostic

# Structured routing/scheduling for this agent is a low-latency constrained-output
# workload. Thinking profiles are intentionally excluded from the family benchmark:
# they are not required by the production design and can consume the output budget
# before a JSON-schema answer is emitted.
diagnostic.QWEN35_PROFILES = tuple(
    profile for profile in diagnostic.QWEN35_PROFILES if not profile.thinking
)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(diagnostic.main()))
