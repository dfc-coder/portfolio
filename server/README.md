# Portfolio assistant

Small local portfolio/CV agent with an explicit, Go-like runtime.

## Runtime

```text
POST /v1/chat/stream
  -> ConversationStore
  -> Agent
      -> Qwen3.5
          -> final answer
          -> or tool_calls
              -> validate registered tool
              -> execute tool
              -> append assistant tool_calls + matching tool results
              -> Qwen3.5 again
  -> SSE response
```

The Agent owns one bounded model/tool loop. There is no semantic router, planner, graph, capability gate, reranker, or agent framework between the request and the model.

## Model

The local runtime uses llama.cpp with the Unsloth GGUF:

```text
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-Q6_K.gguf
```

Thinking mode is disabled for the operational agent loop.

## Tools

Production tools:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` contains the model-facing schema, handler and registry. The registry is the execution source of truth.

Adding a tool should require:

1. define its schema;
2. implement its handler;
3. register one `Tool(schema, handler)` entry.

The Agent does not change when a tool is added.

`set_reminder_mock` is intentionally non-persistent and never sends a notification.

## Files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         explicit bounded model/tool loop
app/tools.py         schemas, handlers, validation, registry
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/prompt.py        production prompt
app/config.py        environment configuration
app/trace.py         diagnostic trace
```

## Runtime rules

- the model chooses among the registered tool schemas;
- the server accepts only registered tool names;
- tool arguments are validated server-side;
- successful identical calls are reused instead of executed twice;
- tool results keep the original `tool_call_id`;
- multiple calls returned in one model round are executed in call order;
- conversation history preserves assistant tool calls and tool results;
- the model/tool loop has a hard round limit.

These are runtime invariants. Behavioral evals measure the local SLM; they do not define the architecture.

## Run

```bash
cp .env.example .env
make models
make up
```

API:

```text
http://localhost:8000
```

Tests:

```bash
make check
make eval-smoke
make eval-strict
```
