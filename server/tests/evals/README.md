# Portfolio agent live evaluation

This evaluation exercises the real running agent end to end through `POST /v1/chat/stream`.

The runtime and the behavioral evaluation are separate concerns. Qwen receives the three production tool schemas directly; there is no classifier, worker routing, ToolSearch, reranker or capability gate.

## Datasets

`agent_cases.jsonl` is the development set. It covers general questions, portfolio retrieval, date/time tasks, reminders, mixed requests and context follow-ups.

`agent_holdout.jsonl` is an untouched holdout set created after the runtime prompt was fixed. Do not use its failures to add phrase-specific prompt rules. If the runtime or prompt is changed after inspecting a holdout failure, replace the affected holdout cases before treating it as an unseen gate again.

Each case contains:

```text
message
optional context
expected tool calls
optional expected arguments/duration
semantic completion criterion
```

Tool selection, arguments, execution and answer presence are checked automatically. `completion` is preserved with the output for semantic review; it is not an exact-string assertion.

## Local model

```text
Qwen3.5-4B
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

Portfolio retrieval uses `Qwen3-Embedding-0.6B` only inside `search_portfolio`.

## Run locally

Start the runtime first:

```bash
make models
make up
make eval-ready
```

Quick check:

```bash
make eval-smoke
```

Development set:

```bash
make eval
```

Strict development gate:

```bash
make eval-strict
```

Run the holdout only after the prompt/runtime is frozen:

```bash
make eval-holdout
```

Run 20 critical development cases five times (100 executions):

```bash
make eval-stability
```

## Metrics

The local runner reports:

```text
overall pass rate
tool selection
argument extraction
tool execution
answer presence
latency p50/p95
pass rate by category
```

The diagnostics trace also records `final_ttft_ms`, total duration, round duration and tool duration.

Free-text correctness, grounding and language preservation must be reviewed against each case's `completion` criterion; the runtime must not be changed merely to match an exact wording.
