# Diego Cano Portfolio

Vue 3 + Vite portfolio with a server-side business representative in Chapter 05.

## Frontend

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Netlify builds the static frontend with `pnpm build` and publishes `dist`.

Set `VITE_AGENT_API_URL` to the public FastAPI URL. Chapter 05 fails closed when the backend URL is missing; it does not simulate the business representative in the browser.

## Business representative

The backend lives in `server/` and keeps Qwen3.5-2B on the infrastructure through `llama-server`; model weights are never loaded by the browser. It also owns session policy and Google Calendar booking confirmation.

```bash
cd server
cp .env.example .env
export LLAMA_MODELS_DIR=/absolute/path/to/models
export LLAMA_MODEL_FILE=Qwen3.5-2B-Q4_K_XL.gguf
docker compose up --build
```

Design and acceptance criteria are in `docs/business-representative/`.
