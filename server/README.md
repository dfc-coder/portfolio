# Portfolio assistant

Small local portfolio/CV assistant with an explicit, Go-like control plane.

## Runtime

```text
POST /v1/chat/stream
  -> ConversationStore
  -> Agent
      -> classify(message, context)
      -> isolated worker
          general   tools=[]
          portfolio tools=[search_portfolio]
          temporal  tools=[resolve_datetime, set_reminder_mock]
      -> one bounded generic model/tool loop
      -> deterministic result composition
  -> SSE response
```

The application owns routing, worker permissions, execution order, validation, termination and conversation state. The model owns natural-language classification, tool selection inside a worker, argument extraction and final wording.

There is no supervisor, planner, critic, graph, semantic tool search, reranker, embedding router or agent framework.

## Model

```text
Qwen3.5-4B
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

Served by llama.cpp with Jinja tool calling and thinking disabled. Portfolio retrieval uses `Qwen3-Embedding-0.6B` only inside `search_portfolio`; embeddings never route or select tools.

## Production tools

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` is the source of truth for schemas, handlers and validation. Adding a tool means defining/registering it and assigning it to the owning worker. The generic worker loop does not change.

## Core files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         explicit orchestrator
app/dispatcher.py    domain classification
app/worker.py        single bounded worker/tool loop
app/tools.py         schemas, handlers, validation, registry
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/prompt.py        classifier + worker prompts
app/config.py        environment configuration
app/trace.py         diagnostic traces
```

## Validation

```bash
make check
make eval-regression
make eval-smoke
```

Full live eval only when explicitly needed:

```bash
make eval-strict
```
