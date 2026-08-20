# Portfolio Business Representative

Server-side conversational representative for the Vue portfolio. FastAPI owns conversation/session policy and Google Calendar side effects; `llama-server` owns Qwen3.5-2B inference.

## Run locally

1. Put the GGUF in a model directory and configure the exact filename.
2. Copy `.env.example` to `.env`.
3. Keep `CALENDAR_MODE=mock` until OAuth is configured.
4. Start the two long-lived services:

```bash
export LLAMA_MODELS_DIR=/absolute/path/to/models
export LLAMA_MODEL_FILE=Qwen3.5-2B-Q4_K_XL.gguf
docker compose up --build
```

FastAPI: `http://localhost:8000`

`llama.cpp` stays inside the compose network unless you explicitly publish it.

## Connect the portfolio

Set at Netlify build time:

```text
VITE_AGENT_API_URL=https://agent-api.example.com
```

The browser then calls only FastAPI. If the variable is absent, the current local corpus provider remains a development fallback.

## Google Calendar

Create a Google OAuth client and obtain a refresh token for the calendar owner with Calendar event and free/busy permissions. Store credentials only in the API environment:

```text
CALENDAR_MODE=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

The LLM can query free/busy and prepare a pending booking, but cannot execute Calendar writes. FastAPI performs the write only after explicit confirmation.

## Tests

```bash
PYTHONPATH=. pytest -q
```
