# Portfolio agent evaluation

Promptfoo is the external behavioral evaluator for the portfolio assistant. It is not part of the production runtime and `app/` never imports it.

## Original baseline

Promptfoo integration started from product commit:

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

After the evaluator isolated product failures, targeted runtime fixes are allowed in separate commits. The evaluator must continue to distinguish transport, retrieval, tool-selection, and answer-quality failures instead of collapsing them into one score.

## Commands

```text
make test        -> deterministic code tests
make cache-check -> verify native Qwen and OpenAI prompt-cache reuse
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
  -> deterministic retrieval/tool assertions
  -> one OpenAI gpt-5.6-luna semantic judge call per case
```

`sse-transform.js` only translates the portfolio SSE protocol. It contains no pass/fail product rules. Retrieval facts are extracted from the normal returned conversation context; a diagnostics trace can be used when available.

## Grading model

The product under test remains Qwen3.5-4B running locally. Semantic answer grading uses `openai:responses:gpt-5.6-luna` with low reasoning effort, so Qwen does not judge itself and cloud grading does not compete with local Qwen for CPU.

Each case now uses exactly one `llm-rubric` assertion for semantic answer quality. The previous `context-recall` and `context-faithfulness` assertions were removed from this suite because Promptfoo 0.122.2 parses those graders through strict textual attribution/verdict formats; a valid judge answer in a different format can produce a false zero. Retrieval coverage is objective for this fixed portfolio corpus, so it is checked deterministically from `output.sources` instead.

The layers are intentionally separate:

```text
retrieval_evidence -> did search_portfolio return the required portfolio evidence?
tool_selection     -> did the agent use or avoid the expected tool?
correctness        -> did the final answer satisfy the case rubric using supplied context?
```

This makes a failed row actionable. A missing Xarlatan source is a retrieval failure; a capability question that calls `search_portfolio` is a tool-selection failure; a grounded but incomplete answer is an answer-quality failure.

Target-agent cases remain serial because llama.cpp runs with `--parallel 1`. Judge assertions are also serial: there is only one model-graded assertion per case, and serial grading makes the first explicit prompt-cache write available before subsequent judge calls.

## Prompt caching

There are three distinct caches.

### Local Qwen KV cache

The llama.cpp service runs with `--cache-prompt`. The product prompt keeps the stable system prompt and tool definitions before request-specific conversation content.

`make cache-check` sends two real requests to llama.cpp using the application's actual system prompt and tool schemas. It reads `timings.cache_n` and `timings.prompt_n` and fails if the second request does not reuse enough prompt tokens.

### OpenAI judge prompt cache

The judge uses a reusable developer policy in `evals/judge-rubric.json`. That policy contains the stable grading contract, scoring rules, and calibrated examples. The case-specific output and rubric are placed in a later user message.

The last content block of the stable developer message has:

```json
{"prompt_cache_breakpoint":{"mode":"explicit"}}
```

and the provider uses:

```yaml
prompt_cache_key: portfolio-eval-judge-v2
prompt_cache_options:
  mode: explicit
  ttl: 30m
```

This follows GPT-5.6 explicit prompt caching: the reusable policy is written once, while changing case data after the breakpoint is not written merely to force a cache hit.

`make cache-check` no longer uses artificial repeated padding. It loads the exact reusable developer policy from `judge-rubric.json`, sends two real Responses API requests, and requires the second request to report at least 1,024 cached input tokens. The same cache key and prefix are used by the real eval, so a cache check can also warm the actual judge prefix.

Every `make eval` and `make eval-edge` writes a local JSON report and prints the number of judge requests plus input, cache-read, and cache-write tokens observed in the real workload.

### Promptfoo result cache

Promptfoo's own response/result cache remains disabled with `evaluateOptions.cache: false` and `--no-cache`. Regression runs must execute fresh Qwen and judge calls; this setting does not disable llama.cpp KV caching or OpenAI provider-native prompt caching.

## Result artifacts

Exported reports are host files:

```text
server/evals/results/latest-regression.json
server/evals/results/latest-edge.json
```

The Promptfoo container mounts that directory at `/results`. Internal Promptfoo state remains under `evals/.promptfoo`.

## Cloud judge credentials

For local development, `server/.env` may contain:

```text
OPENAI_API_KEY=sk-...
```

The repository ignores `.env`. The API service explicitly overrides `OPENAI_API_KEY` to an empty value, so the credential is not exposed to the application container; `evals/compose.yaml` passes it only to Promptfoo. Exporting the variable in the shell is also supported.

## Product findings addressed after evaluator calibration

The first cloud run exposed two independent product problems.

Retrieval ranked lexical overlap before embedding similarity. Queries that unnecessarily included the portfolio subject's name could therefore promote `owner.name` and generic employment documents over the relevant project, education, or certification. Retrieval now ranks semantic similarity first and uses lexical overlap only as a tie-breaker.

The local model also called `search_portfolio` for a pure assistant-capability question and produced retrieval queries containing the subject's name despite existing guidance. The system prompt now states both rules explicitly: capability-only questions never need tools, and portfolio searches use short topic-only queries unless identity itself is requested.

## Case lifecycle

A new failure discovered during manual use should first become an `EDGE:` case. Diagnose the failing layer before changing product behavior.

```text
manual failure
  -> add EDGE case
  -> reproduce
  -> identify transport / retrieval / routing / answer layer
  -> make one targeted product change
  -> run deterministic tests
  -> run cache-check when prompt/runtime caching changed
  -> run REG and EDGE evaluations
```

Once important behavior is stable, promote the case to `REG:`.

## Constraints

- Evaluation stays outside `app/`.
- The SSE adapter only normalizes transport data.
- Retrieval and tool behavior use deterministic assertions when the expected evidence is objective.
- Semantic answer quality uses one independent cloud judge call per case.
- Promptfoo result caching stays off for regression runs.
- Promptfoo version is pinned.
- Product changes must be traceable to a diagnosed evaluator failure.
