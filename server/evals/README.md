# Portfolio agent evaluation

Promptfoo is the external behavioral evaluator for the portfolio assistant. It is not part of the production runtime and `app/` must never import it.

## Frozen product baseline

The product state being evaluated was frozen before Promptfoo integration at commit:

```text
cbc8a0e0758cf50e0481610a50f629be447725c7
```

Runtime configuration at that baseline:

```text
LLM:             Qwen3.5-4B / Qwen3.5-4B-UD-Q4_K_XL.gguf
Embeddings:      Qwen3-Embedding-0.6B / Qwen3-Embedding-0.6B-Q8_0.gguf
Temperature:     0.70
Top-p:           0.80
Top-k:           20
Presence penalty:1.5
Repeat penalty:  1.0
Retrieval top-k: 4 documents
```

The commit SHA is the authoritative source baseline. Promptfoo integration commits do not modify `app/`.

## Why this exists

`pytest` checks deterministic code behavior. Promptfoo checks probabilistic product behavior against the real API.

```text
make test        -> code correctness
make cache-check -> prompt-cache mechanisms really reuse prefixes
make eval        -> stable behavioral regression cases
make eval-edge   -> repeated edge cases
```

Promptfoo is pinned to `0.122.2` in `evals/compose.yaml`.

## Architecture

```text
Promptfoo
  -> POST http://api:8000/v1/chat/stream
  -> real Agent / local Qwen / tools / retrieval
  -> SSE response
  -> sse-transform.js
  -> { answer, context, sources, tools, trace }
  -> deterministic assertions
  -> OpenAI gpt-5.6-luna cloud judge for model-graded assertions
```

`sse-transform.js` only translates the portfolio SSE protocol. It contains no pass/fail business rules. Retrieval facts are extracted from the returned conversation context, which is part of the normal API contract. If a diagnostics trace is available, the adapter can use it as the richer source instead.

## Grading

The product under test remains Qwen3.5-4B running locally. Model-graded assertions use `openai:responses:gpt-5.6-luna` with low reasoning effort, so the model under test no longer judges itself and cloud grading does not compete with local Qwen for CPU.

Target-agent cases remain serial because the local llama.cpp server is configured with `--parallel 1`. Cloud model-graded assertions may use up to three concurrent requests. There is intentionally no per-eval-step timeout: that timeout previously forced every slow row to fail after 180 seconds and disabled Promptfoo's grading grouping.

The first cloud-judge report must still reproduce the behavior already known from manual inspection:

```text
Known good:
- portfolio_go
- portfolio_systemg
- mixed_two_portfolio_facts final answer

Known product failures:
- portfolio_rust retrieval/completeness
- portfolio_education retrieval/completeness
- portfolio_owasp_cert retrieval/correctness

Known unstable behavior:
- capability questions after small talk/thanks may call search_portfolio unnecessarily
```

If the cloud judge cannot distinguish those known cases, change only the grader provider. Keep the dataset, SSE adapter, product API and target runtime unchanged while calibrating the evaluator.

## Prompt caching

There are three different caches and they must not be confused.

### Local Qwen KV cache

The llama.cpp service runs with `--cache-prompt`. The product prompt keeps the stable system prompt and tool definitions before conversation-specific content, which gives llama.cpp a reusable prefix across requests and an even larger reusable prefix across tool rounds.

`make cache-check` sends two real requests to the running llama service using the application's system prompt and tool schemas. It reads llama.cpp's `timings.cache_n` and `timings.prompt_n` counters and fails unless the second request actually reuses prompt tokens. This verifies cache reuse rather than merely checking configuration text.

### OpenAI judge prompt cache

The judge provider uses GPT-5.6 Luna with a stable `prompt_cache_key` and native OpenAI prompt-cache options. GPT-5.6 requires an eligible shared prefix of at least 1,024 visible input tokens. Short grading prompts therefore may legitimately have no cache hit.

`make cache-check` performs a separate OpenAI Responses API probe with an explicit reusable prefix above that threshold and fails unless the second request reports cached input tokens. This verifies that native caching works for the configured account/model/API path.

Every `make eval` and `make eval-edge` also writes a local JSON result and reports the cache tokens Promptfoo observed from the real grader workload. A zero hit rate is diagnostic, not automatically a test failure: do not pad grader prompts or change grading semantics only to cross the 1,024-token threshold. Cache optimization is useful only when the real reusable prefix is long enough to save cost or latency.

### Promptfoo result cache

Promptfoo's own response/result cache remains disabled with `evaluateOptions.cache: false` and `--no-cache`. That is intentional: regression runs must execute fresh Qwen and judge calls instead of replaying previous outputs. Disabling Promptfoo's result cache does not disable llama.cpp KV caching or OpenAI's provider-native prompt cache.

## Result artifacts

Promptfoo keeps its internal state under `evals/.promptfoo`, but exported JSON reports are written to a separate host directory so they are easy to inspect and script against:

```text
server/evals/results/latest-regression.json
server/evals/results/latest-edge.json
```

Inside the Promptfoo container that directory is mounted as `/results`. `make eval` and `make eval-edge` create the host directory automatically before launching the container. Generated reports are ignored by Git.

## Cloud judge credentials

For local development, `server/.env` may contain:

```text
OPENAI_API_KEY=sk-...
```

The repository ignores `.env`. The API service explicitly overrides `OPENAI_API_KEY` to an empty value, so the credential is not exposed to the application container; `evals/compose.yaml` passes it only to Promptfoo. Exporting the variable in the shell is also supported.

`make eval`, `make eval-edge`, and `make cache-check` fail immediately when the variable is missing.

## Optional local diagnostics

`server/.env` may contain a non-empty diagnostics token if you also want the evaluator to capture the internal diagnostic trace:

```text
AGENT_DIAGNOSTICS_TOKEN=some-local-only-value
```

This is optional for normal evaluation. The evaluator obtains retrieval context from the normal SSE `context` event when no trace is exposed. Keep the token empty in deployed environments unless diagnostics are explicitly required.

## Commands

Start the current runtime normally:

```bash
make up
```

Verify both native prompt-cache mechanisms:

```bash
make cache-check
```

Run the stable regression suite:

```bash
make eval
```

Run repeated edge cases:

```bash
make eval-edge
```

Open the local Promptfoo result viewer:

```bash
make eval-view
```

Then open `http://localhost:3000`.

## Case lifecycle

A new failure discovered while manually testing the agent is added first as an `EDGE:` case and repeated five times. Do not patch the agent first.

```text
manual failure
  -> add EDGE case
  -> reproduce
  -> identify failing layer
  -> make one product change
  -> make test
  -> make cache-check when prompt/runtime caching changed
  -> make eval
  -> make eval-edge
```

Once an edge case is stable and important, promote it to a `REG:` case so it becomes a permanent regression check.

## Go-like rules

- Evaluation stays outside `app/`.
- No evaluator factories, registries, workers or framework wrappers.
- No custom semantic scoring code.
- The SSE adapter only normalizes transport data.
- Test cases are data in `cases.yaml`.
- One command per purpose.
- Promptfoo version is pinned.
- Product changes and evaluator changes are never mixed when diagnosing a regression.
