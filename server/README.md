# Portfolio assistant

Small local portfolio/CV assistant with an explicit, Go-like control plane.

## Runtime

```text
POST /v1/chat/stream
  -> ConversationStore
  -> Agent / orchestrator
      -> classify(message, context)
      -> run one or more isolated workers
          -> general   tools=[]
          -> portfolio tools=[search_portfolio]
          -> temporal  tools=[resolve_datetime, set_reminder_mock]
      -> validate structured WorkerResult values
      -> compose results deterministically
  -> SSE response
```

The application owns routing, worker permissions, execution order, termination, validation and conversation state. The model handles natural-language classification, tool selection inside a worker, argument extraction and answer generation.

Workers never call each other and never choose another worker. There is no supervisor agent, planner, critic, semantic router, embedding router, reranker, capability scorer or agent framework.

All workers use the same llama.cpp model instance. Workers are logical configurations: one prompt plus an explicit subset of tools.

## Control-plane invariants

- `classify()` only returns structured routes and never executes tools;
- the orchestrator owns control flow and state;
- workers are stateless and isolated by tool permissions;
- general never receives tools;
- portfolio receives only `search_portfolio`;
- temporal receives only `resolve_datetime` and `set_reminder_mock`;
- workers return a structured `WorkerResult`, not an SSE response;
- worker model output is JSON (`{"answer":"..."}`) and is validated before presentation;
- workers never communicate with each other;
- mixed requests are fan-out plus deterministic result composition;
- there is one bounded model/tool loop implementation;
- tool arguments are validated server-side;
- successful identical tool calls are reused instead of executed twice;
- the model/tool loop has a hard round limit.

## Model

The model is selected through `.env` and served by llama.cpp with `--jinja` and thinking disabled.

The current local evaluation target is the Unsloth quantized model:

```text
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-UD-Q6_K_XL.gguf
```

The routed-worker architecture should be evaluated with the existing 2B baseline first. A larger model can then be tested as a separate variable if argument extraction is still below target.

## Tools

Production tools:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` remains the execution source of truth for schemas, handlers and validation.

Adding a tool requires implementing/registering the tool and assigning its schema to the worker that owns that domain. The classifier and worker runner do not change.

`set_reminder_mock` is intentionally non-persistent and never sends a notification.

## Files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         explicit orchestrator
app/dispatcher.py    structured domain classification
app/worker.py        one bounded worker/tool runtime
app/tools.py         schemas, handlers, validation, registry
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/prompt.py        classifier + worker prompts
app/config.py        environment configuration
app/trace.py         diagnostic traces
```

## Run

If the model is already present locally, point `LLAMA_MODELS_DIR` and `LLAMA_MODEL_FILE` in `.env` to it and skip `make models`.

```bash
make up
make eval-ready
```

API:

```text
http://localhost:8000
```

Unit tests:

```bash
make check
```

Current four-case regression:

```bash
uv run python tests/evals/run_agent_eval.py \
  --case general_hello \
  --case general_joke \
  --case date_tomorrow \
  --case date_one_week \
  --strict
```

Smoke:

```bash
make eval-smoke
```

Full live eval:

```bash
make eval-strict
```
