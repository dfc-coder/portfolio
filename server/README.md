# Portfolio assistant

This server is a small OpenAI-compatible agent running on Qwen through llama.cpp.

## Runtime flow

```text
POST /v1/chat/stream
  -> Agent
      -> Qwen
          -> final answer
          -> or tool_calls
              -> execute tools
              -> append assistant tool_calls + matching tool results
              -> Qwen again
  -> SSE response
```

Available tools:

```text
search_portfolio
get_current_datetime
add_duration_to_datetime
set_reminder_mock
```

`set_reminder_mock` is intentionally non-persistent. It exists to exercise a safe multi-round tool chain without adding a scheduler, database or calendar.

## Application files

```text
app/main.py        # composition and FastAPI
app/api/router.py  # HTTP/SSE boundary
app/agent.py       # explicit bounded tool loop
app/tools.py       # explicit schemas, validation and tool execution
app/portfolio.py   # portfolio retrieval
app/prompt.py      # production prompt
app/config.py      # application environment configuration
```

There is no planner, graph, tool registry, agent framework or server-side conversation store. The browser round-trips a bounded hidden OpenAI-compatible conversation context with each request, including assistant `tool_calls`, tool results, and final assistant messages.

Date/time fallback configuration belongs to the date capability through the standard `TZ` environment variable. It is not Agent state. Qwen thinking mode is disabled; operational model execution is reported separately from model reasoning.

## Run

```bash
cp .env.example .env
make up
```

API: `http://localhost:8000`
