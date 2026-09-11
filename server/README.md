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

## Models

```text
Qwen3.5-4B / Qwen3.5-4B-UD-Q4_K_XL.gguf
Qwen3-Embedding-0.6B / Qwen3-Embedding-0.6B-Q8_0.gguf
```

llama.cpp serves both models. Thinking is disabled for Qwen. Embeddings are used only by `search_portfolio`.

## Production tools

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` contains the model-facing schemas, validation and explicit dispatch. There is no secondary tool registry.

## Core files

```text
app/main.py          composition root / FastAPI
app/api/router.py    HTTP + SSE boundary
app/agent.py         streamed model/tool loop
app/tools.py         tool schemas, validation and execution
app/prompt.py        system prompt
app/conversation.py  bounded in-memory conversation state
app/portfolio.py     portfolio retrieval
app/trace.py         diagnostics only
app/config.py        environment configuration
```

## Commands

```bash
make install     # Python dependencies
make models      # verified GGUF downloads
make test        # deterministic tests
make up          # local stack
make eval        # Promptfoo regression suite
make eval-edge   # repeated edge cases
make eval-view   # Promptfoo local viewer
make verify      # test + models + stack + regression eval
```

Promptfoo is isolated under `evals/` and is not a production dependency. Its configuration, frozen baseline and case lifecycle are documented in `evals/README.md`.
