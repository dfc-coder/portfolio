# Portfolio Business Representative

Server-side **Bounded Reflective ReAct** representative optimized for Qwen3.5-0.8B. FastAPI owns workflow state, verification and Google Calendar side effects. Two small llama.cpp services remain resident server-side:

- `llama`: Qwen3.5-0.8B for structured planning, routing fallback and natural-language rendering.
- `reranker`: Qwen3-Reranker-0.6B for state-aware zero-shot semantic routing.

The browser never downloads model weights.

## Architecture

```text
visitor + compact state
        |
        v
Qwen3-Reranker-0.6B
        |
        +-- high-confidence --> domain + relation
        |
        +-- ambiguous -------> Qwen 0.8B constrained routing judge
                                |
                                v
                         domain + relation
                                |
               +----------------+----------------+
               |                                 |
        business/general                   scheduling
               |                                 |
      grounded Qwen stream                  bounded FSM
               |                                 |
      rolling safety guard                  micro-planner
               |                                 |
              SSE                            executor
                                                 |
                                             verifier
                                                 |
                                         deterministic text
```

Routing uses semantic route descriptions, not keyword/regex intent rules. Deterministic code remains authoritative only for workflow and safety invariants such as valid offered slots, explicit confirmation and Calendar writes.

`SessionState.current_focus` is separate from `SessionState.active_workflow`. A visitor can interrupt an active scheduling workflow with a business/general question and later resume the same offered slots.

```text
app/
  api/             HTTP + SSE boundary
  agent/           semantic router, FSM, planner, executor, verifier, renderer
  domain/          conversation, routing, planning and scheduling types
  scheduling/      scheduling policy and slot calculation
  ports/           LLM, reranker, calendar and session interfaces
  infrastructure/  llama.cpp LLM/reranker, Google Calendar, OAuth, config, sessions
  bootstrap.py     composition root
```

Legacy top-level modules such as `app.profile` and `app.slot_service` are thin compatibility exports only.

## Safe real streaming

Business and general knowledge answers use llama.cpp with `stream=true` end-to-end. The backend does not wait for a complete answer and does not replay completed text with artificial delays.

A small rolling character holdback sits between the model stream and SSE. It exists only to prevent restricted operational claims from crossing the HTTP boundary, including owner impersonation and generated claims that a meeting was booked, scheduled, placed on the calendar, or that an invitation was sent. It adds no timer or animation.

Owner-specific claims are grounded by prompt contract against `BUSINESS_CONTEXT`: the renderer is instructed to use only explicitly supplied profile facts and to abstain when the requested fact is absent. Calendar side effects remain unreachable from the informational renderer.

Scheduling output is intentionally different: slots, confirmation prompts and booking results are deterministic Python text and are emitted atomically. Only the Calendar workflow can report a successful booking, and only after the Calendar write succeeds.

The completed streamed answer is checked again by the lightweight deterministic verifier for telemetry. This post-stream check never delays or rewrites content already sent to the visitor.

## Required models

Place both GGUF files in `LLAMA_MODELS_DIR` (defaults to `server/models`):

```text
Qwen3.5-0.8B-UD-Q4_K_XL.gguf
qwen3-reranker-0.6b-q8_0.gguf
```

The main model filename is configurable with `LLAMA_MODEL_FILE`; the router model is configurable with `RERANKER_MODEL_FILE`.

For llama.cpp, the reranker service starts with:

```text
--embedding --rerank --pooling rank
```

and FastAPI calls `/v1/rerank` with only three route descriptions per turn. No embedder or vector database is required for the current three-domain router.

## Run locally

```bash
cp .env.example .env
make doctor
make up
```

FastAPI: `http://localhost:8000`

Readiness checks both resident models:

```bash
make ready
```

Expected shape:

```json
{"status":"ok","llama":"ready","reranker":"ready"}
```

Useful commands:

```bash
make logs
make logs-reranker
make models
make check
```

For production, pin `LLAMA_IMAGE` to a known llama.cpp tag or image digest rather than relying on the floating `server` tag.

## Routing cascade

The router evaluates three stable semantic candidates at a time. With no active workflow they are business, scheduling and general `NEW` routes. With an active scheduling workflow they become business/general `INTERRUPT` and scheduling `CONTINUE` routes.

`ROUTER_MIN_SCORE` and `ROUTER_MIN_MARGIN` are operational bootstrap defaults, not calibrated probabilities. If the top score is weak or the top-two margin is small, routing escalates to the already-resident Qwen 0.8B model using constrained JSON.

The semantic router sees only a compact state projection: current focus, active workflow, workflow stage, whether slots or a pending booking exist, the last assistant message and the latest visitor message.

## Qwen profiles

Planner, renderer, repair and routing judge use independent sampling settings. Defaults are configurable in `.env`.

Thinking remains disabled. Structured outputs are validated again before actions execute.

## Google Calendar

```text
CALENDAR_MODE=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

The LLM never owns the destructive Calendar write. A booking is created only after explicit confirmation, and the selected slot must come from a previously offered availability result.

## Tests

```bash
make check
```

Coverage includes semantic routing cascade behavior, ambiguous-route fallback, guarded real-stream output, scheduling interruptions/resumption, slot validation and explicit booking confirmation.
