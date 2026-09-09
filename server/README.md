# Portfolio assistant

Small local portfolio/CV assistant with an explicit, Go-like control plane.

## Runtime

```text
POST /v1/chat/stream
  -> ConversationStore
  -> Agent / orchestrator
      -> classify(message, context)
      -> run one or more isolated paths
          -> general   -> GeneralWorker, no tools
          -> portfolio -> PortfolioWorker, search_portfolio native tool
          -> datetime  -> structured arguments -> validate -> resolve_datetime
          -> reminder  -> structured arguments -> validate -> set_reminder_mock
      -> deterministic temporal formatting
      -> compose results
  -> SSE response
```

Python owns routing, execution order, validation, tool execution, termination, formatting for deterministic temporal operations, and conversation state. The model owns natural-language classification and semantic argument extraction.

Workers never call each other and never choose another worker. There is no supervisor agent, planner, critic, semantic router, embedding router, reranker, capability scorer, or agent framework.

## Control-plane invariants

- `classify()` only returns structured routes and never executes operations;
- routes are `general`, `portfolio`, `datetime`, and `reminder`;
- the orchestrator owns control flow and state;
- general receives no tools;
- portfolio receives only `search_portfolio` through the native tool protocol;
- datetime and reminder receive no native tool schemas;
- datetime and reminder return closed structured arguments;
- Python validates those arguments and calls the deterministic function directly;
- datetime and reminder do not perform a second model call for final prose;
- workers never communicate with each other;
- mixed requests are explicit fan-out plus deterministic result composition;
- the portfolio tool loop remains bounded and reuses identical successful calls.

## Model

The model is selected through `.env` and served by llama.cpp with thinking disabled.

The current correctness baseline is:

```text
unsloth/Qwen3.5-4B-GGUF
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

The frozen local baseline before the temporal fast path passed the 10-case smoke gate with 10/10 selection, 8/8 argument extraction, and 10/10 tool execution.

Generation baseline:

```text
temperature = 0.70
top_p = 0.80
top_k = 20
min_p = 0.0
presence_penalty = 1.5
repeat_penalty = 1.0
max_tokens = 256
```

## Operations

Production operations:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` remains the execution source of truth for operation handlers and validation helpers. `search_portfolio` still uses the native model tool protocol. `resolve_datetime` and `set_reminder_mock` are invoked directly after structured semantic parsing.

`set_reminder_mock` is intentionally non-persistent and never sends a notification.

## Files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         explicit orchestrator
app/dispatcher.py    structured domain classification
app/worker.py        bounded native worker/tool runtime for general/portfolio
app/temporal.py      structured datetime/reminder fast path
app/tools.py         schemas, handlers, validation, registry
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/prompt.py        classifier + worker/parser prompts
app/config.py        environment configuration
app/trace.py         diagnostic traces
```

## Run

If the 4B model is already present locally, keep your existing `.env` and skip `make models`.

```bash
make check
make down
make up
```

API:

```text
http://localhost:8000
```

Four-case regression:

```bash
make eval-regression
```

Smoke acceptance gate:

```bash
make eval-smoke
```

M5 is accepted only when the smoke gate remains 10/10. Compare its p50/p95 to the frozen M0 baseline of approximately 31.17 s / 91.71 s.

Quick summary:

```bash
jq '.summary | {cases,passed,tool_selection_rate,parameter_extraction_rate,tool_execution_success_rate,latency_p50_ms,latency_p95_ms}' tests/evals/results/smoke.json
```

Per-case latency and route:

```bash
jq '.cases[] | {id, latency_ms, routes: .trace.dispatch.routes, calls: .actual_calls}' tests/evals/results/smoke.json
```

Full live eval:

```bash
make eval-strict
```
