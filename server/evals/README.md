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
make test       -> code correctness
make eval       -> stable behavioral regression cases
make eval-edge  -> repeated edge cases
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

## Cloud judge credentials

Do not put the OpenAI API key in `server/.env`: that file is also loaded by the production-like API container. Export the key only in the shell that launches Promptfoo:

```bash
export OPENAI_API_KEY='sk-...'
```

`make eval` and `make eval-edge` fail immediately when the variable is missing. The key is passed only to the Promptfoo service by `evals/compose.yaml`.

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

Run the stable regression suite:

```bash
export OPENAI_API_KEY='sk-...'
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
