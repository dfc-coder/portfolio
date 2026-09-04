# Portfolio assistant

This server does one thing: answer questions about the portfolio/CV from the supplied profile.

## Runtime flow

```text
POST /v1/chat/stream
  -> PortfolioAgent
      -> OpenAI SDK -> llama.cpp embeddings -> relevant profile facts
      -> prompt + history + facts
      -> OpenAI SDK -> llama.cpp/Qwen chat stream
  -> SSE tokens
```

## Application files

```text
app/main.py        # composition and FastAPI
app/api/router.py  # HTTP/SSE boundary
app/agent.py       # retrieval + response flow
app/prompt.py      # production prompt
app/config.py      # environment configuration
```

There is no router, scheduler, calendar, tool framework, server-side conversation store, custom LLM client or custom embedding client.

The browser sends the visible conversation history with each request, so the server remains stateless between turns.

## Run

```bash
cp .env.example .env
make up
```

API: `http://localhost:8000`
