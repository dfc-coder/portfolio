# Portfolio agent live evaluation

This evaluation exercises the real running portfolio agent end to end through `POST /v1/chat/stream`.
It evaluates model tool decisions, argument extraction, deterministic tool execution and final response generation.

The runtime architecture is deliberately independent of these behavioral evals. The local Qwen model receives the registered production tool schemas directly; there is no ToolSearch, capability gate or reranker.

## Dataset

`agent_cases.jsonl` contains 50 initial validation cases covering:

- general/capability questions
- portfolio retrieval
- date/time tasks
- reminders
- mixed intents
- context follow-ups and reuse of prior tool results

Each case contains the user message, optional OpenAI-compatible context, expected tool calls, forbidden tool calls and a semantic reference in `completion`.

## Local model

The live gate runs llama.cpp with:

```text
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-Q6_K.gguf
```

Portfolio retrieval continues to use `Qwen3-Embedding-0.6B`.

## Run locally

Start the server first:

```bash
make up
```

Run the focused smoke check:

```bash
make eval-smoke
```

Run the complete checkpoint:

```bash
make eval
```

Strict full mode exits non-zero if any case fails:

```bash
make eval-strict
```

Override the server URL when needed:

```bash
AGENT_API_URL=http://localhost:8000 make eval-smoke
```

Outputs are written to:

```text
tests/evals/results/latest.json
tests/evals/results/qwencloud.jsonl
tests/evals/results/smoke.json
tests/evals/results/smoke-qwencloud.jsonl
```

## Local deterministic metrics

The runner reports:

- overall pass rate
- exact expected tool calls
- tool argument correctness
- tool execution success
- final-answer presence
- latency p50 and p95
- pass rate by category

Tool behavior is evaluated locally because it is directly observable.

## Semantic evaluation

`qwencloud.jsonl` contains `prompt`, `output` and `completion` records for optional semantic judging of final-answer correctness and response quality. Semantic judging does not decide runtime routing or tool eligibility.
