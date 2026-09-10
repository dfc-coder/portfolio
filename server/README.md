# Portfolio assistant

Small local portfolio/CV assistant with an explicit, Go-like runtime.

## Runtime

```text
POST /v1/chat/stream
  -> ConversationStore
  -> Agent
      -> Qwen + [search_portfolio, resolve_datetime, set_reminder_mock]
      -> final text: stream tokens to the visitor
      -> tool call: execute -> append result -> next Qwen round
  -> SSE response
```

There is one agent, one system prompt and one bounded tool loop. There is no classifier, domain routing, worker abstraction, supervisor, planner, critic, graph, semantic tool search, reranker or agent framework.

## Model

```text
Qwen3.5-4B
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

Served by llama.cpp with Jinja tool calling and thinking disabled. Portfolio retrieval uses `Qwen3-Embedding-0.6B` only inside `search_portfolio`.

## Production tools

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` contains the model-facing schemas, argument validation and the explicit `execute_tool()` dispatch. There is no secondary tool registry.

## Core files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         one streamed model/tool loop
app/tools.py         schemas, validation and execution
app/prompt.py        one system prompt
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/config.py        environment configuration
```

## Validation

Deterministic runtime and integration tests:

```bash
make check
```

Start the local runtime and run live Qwen evaluation only after deterministic tests pass:

```bash
make models
make up
make eval-ready
make eval-smoke
make eval-strict
```

The smoke suite is a quick check only. Acceptance criteria are defined in `../docs/portfolio-assistant/DOD-agent-runtime-minimo.md`.
