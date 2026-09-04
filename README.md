# Diego Cano Portfolio

Vue 3 + Vite portfolio with a server-side Qwen portfolio assistant in Chapter 05.

## Frontend

The frontend uses pnpm as its only package manager.

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Netlify builds the static frontend with `pnpm build` and publishes `dist`.

Set `VITE_AGENT_API_URL` to the public FastAPI URL. Chapter 05 talks to the server-side portfolio assistant; there is no browser-side model or simulated agent.

## Portfolio assistant

The backend lives in `server/` and runs Qwen through llama.cpp's OpenAI-compatible API. The agent uses a small bounded multi-tool loop with these capabilities:

```text
search_portfolio
get_current_datetime
add_duration_to_datetime
set_reminder_mock
```

The backend is stateless. The browser round-trips a bounded hidden OpenAI-compatible conversation context, including tool calls and tool results. There is no planner, graph, registry, server-side session store, scheduler, calendar integration, or persistent reminder service.

Qwen thinking mode is disabled.

```bash
cd server
cp .env.example .env
export LLAMA_MODELS_DIR=/absolute/path/to/models
export LLAMA_MODEL_FILE=Qwen3.5-2B-UD-Q6_K_XL.gguf
make up
```

Architecture notes are in `docs/portfolio-assistant/`.
