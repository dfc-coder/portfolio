# Portfolio Business Representative

Server-side **Bounded Reflective ReAct** representative optimized for Qwen3.5-0.8B. FastAPI owns workflow state, verification and Google Calendar side effects; llama.cpp is used only for small structured planning decisions and business-language rendering.

## Architecture

```text
HTTP/SSE
  -> BusinessRepresentative
      -> deterministic FSM
      -> StructuredPlanner (Qwen, JSON schema)
      -> AgentVerifier
      -> ActionExecutor
      -> Observation
      -> triggered one-shot repair when validation fails
      -> HybridRenderer
```

The scheduling workflow is state-first. Follow-ups such as `el segundo`, `my email is ...` or `sí, confirmo` are resolved from structured session state instead of re-detecting scheduling intent from each message.

```text
app/
  api/             HTTP + SSE boundary
  agent/           FSM, planner, executor, verifier, renderer
  domain/          conversation, planning and scheduling types
  scheduling/      scheduling policy and slot calculation
  ports/           LLM, calendar and session interfaces
  infrastructure/  llama.cpp, Google Calendar, OAuth, config, session store
  bootstrap.py     composition root
```

Legacy top-level modules such as `app.profile` and `app.slot_service` are thin compatibility exports only.

## Run locally

1. Put the GGUF in a model directory.
2. Copy `.env.example` to `.env`.
3. Keep `CALENDAR_MODE=mock` until OAuth is configured.
4. Start the services:

```bash
export LLAMA_MODELS_DIR=/absolute/path/to/models
export LLAMA_MODEL_FILE=Qwen3.5-0.8B-UD-Q4_K_XL.gguf
docker compose up --build
```

FastAPI: `http://localhost:8000`

For production, pin `LLAMA_IMAGE` to a known llama.cpp tag or image digest rather than relying on the floating `server` tag.

## Qwen profiles

Planner, renderer and repair use independent sampling settings. Defaults are configurable in `.env`:

```text
PLANNER_TEMPERATURE=0.15
PLANNER_MAX_TOKENS=96
RENDERER_TEMPERATURE=0.65
RENDERER_MAX_TOKENS=180
REPAIR_TEMPERATURE=0.10
REPAIR_MAX_TOKENS=96
AGENT_MAX_STEPS=3
AGENT_MAX_REPAIRS=1
```

Thinking remains disabled. The planner requests constrained JSON output and Pydantic validates it again before any action executes.

## Google Calendar

```text
CALENDAR_MODE=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

The LLM never owns the destructive Calendar write. A booking is created only when a pending booking exists and the next visitor message is an explicit confirmation.

## Tests

```bash
PYTHONPATH=. pytest -q
```

The suite separates deterministic FSM/executor/verifier tests from end-to-end conversation regressions.
