# Diego Cano Portfolio

Vue 3 + Vite portfolio with a server-side Qwen portfolio assistant.

## Frontend

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Netlify builds the static frontend with `pnpm build` and publishes `dist`.

Set `VITE_AGENT_API_URL` to the public FastAPI URL. The browser talks to the server-side assistant; there is no browser-side model.

## Portfolio assistant

The backend lives in `server/` and runs `Qwen3.5-4B` through llama.cpp. It has one agent, one bounded tool loop and three tools:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

Conversation state is bounded and kept in memory by the server. Portfolio retrieval uses `Qwen3-Embedding-0.6B`.

```bash
cd server
cp .env.example .env
make models
make up
make test
make eval
```

Runtime details are in `server/README.md`. Behavioral evaluation is in `server/evals/README.md`.
