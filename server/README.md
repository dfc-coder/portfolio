# Portfolio Assistant

The server has one job: answer questions about the portfolio/CV using the configured profile.

## Flow

```text
POST /v1/chat/stream
        ↓
PortfolioAgent
        ↓
PortfolioSearch ──→ Embeddings
        ↓
relevant profile facts
        ↓
build_messages()
        ↓
Qwen / llama.cpp
        ↓
SSE tokens
```

There is no scheduling, calendar integration, action execution, router, planner, tool framework or agent graph.

## App files

- `app/main.py`: builds the application and dependencies.
- `app/api.py`: exposes the streaming chat endpoint.
- `app/agent.py`: owns the single request flow.
- `app/prompt.py`: canonical production prompt and message construction.
- `app/search.py`: embeds and retrieves relevant profile facts.
- `app/profile.py`: loads the JSON profile.
- `app/sessions.py`: keeps short conversation history in memory.
- `app/llm.py`: streams responses from llama.cpp.
- `app/embeddings.py`: talks to the embedding model.
- `app/settings.py`: environment configuration.

## Run

```bash
make test
make up
```
