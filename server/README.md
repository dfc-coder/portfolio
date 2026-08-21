# Portfolio Business Representative

Server-side business representative optimized for Qwen3.5-0.8B. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: Qwen3.5-0.8B for scheduling extraction, ambiguous-route fallback and grounded response generation.
- `reranker`: Qwen3-Reranker-0.6B for dataset-free semantic routing.

## Architecture

```text
visitor
  |
  v
SemanticRouter
reranker -> Qwen judge only on ambiguity
  |
  +---------------- BUSINESS / GENERAL ----------------+
  |                                                    |
  |                                              Responder
  |                                          grounded real stream
  |                                                    |
  |                                                StreamGuard
  |                                                    |
  |                                                   SSE
  |
  +---------------- SCHEDULING ------------------------+
                         |
                      Scheduler
                 structured turn extraction
                         |
                  SchedulingMemory
                    facts, no stages
                         |
              +----------+----------+
              |                     |
         deterministic reply    CalendarPort
                                   |
                          availability / booking
```

The application intentionally does **not** contain a conversational FSM, capability registry, generic tool selector or generic ReAct loop. Those abstractions were removed because the current product has one bounded workflow and two real Calendar operations; they created more coordination points than value.

`server/app/agent` contains only:

```text
representative.py  thin orchestration
router.py          BUSINESS / SCHEDULING / GENERAL routing
scheduler.py       meeting workflow + hard write invariants
responder.py       grounded knowledge streaming
stream_guard.py    narrow rolling output safety boundary
```

External boundaries remain separated under `ports/` and `infrastructure/`.

## Scheduling model

Scheduling is represented by facts in `SchedulingMemory`:

```text
requested_start_date
requested_end_date
offered_slots
selected_slot_id
visitor_name
visitor_email
subject
pending_booking
```

There are no `DATES -> SLOT -> DETAILS -> CONFIRMATION` conversation states. The scheduler looks at the structured memory and the latest extracted scheduling turn, then performs the next necessary operation.

The only external Calendar operations are:

```text
read:  search availability
write: create a prepared booking
```

The write remains deterministic and guarded:

1. the slot must have been offered in this session;
2. visitor details must exist and email must be valid;
3. a `PendingBooking` must exist;
4. the latest visitor message must satisfy explicit-confirmation policy;
5. booking success is reported only after Calendar returns success.

A business/general interruption does not clear `SchedulingMemory`, so the visitor can resume the meeting later.

## Routing

The router evaluates three semantic descriptions. During an active meeting task the candidates become scheduling continuation versus business/general interruption.

```text
reranker
   |
   +-- clear margin --> route
   |
   +-- ambiguous ----> Qwen 0.8B constrained route choice
```

If the router sends a false positive into scheduling, `Scheduler` can return `not_applicable`; the representative then reroutes only between business and general without destroying meeting memory.

A trained classifier is intentionally deferred until reviewed real examples exist. The reranker remains useful now because there is no training dataset and only three route candidates.

## Safe real streaming

Business/general answers use llama.cpp with `stream=true` end-to-end. There is no post-completion typewriter effect.

`StreamGuard` keeps a tiny rolling holdback and blocks only narrow operational claims such as owner impersonation or claiming that a Calendar action already completed. It does **not** block capability descriptions such as "I can schedule a meeting after you confirm."

The knowledge responder receives both:

- `BUSINESS_CONTEXT`: authoritative owner/project facts;
- `AGENT_CAPABILITIES`: authoritative actions the scheduler can actually perform.

Therefore the assistant can accurately answer questions such as "¿Podés usar herramientas?" without giving the free-form renderer permission to execute side effects.

## Required models

Place both GGUF files in `LLAMA_MODELS_DIR` (defaults to `server/models`):

```text
Qwen3.5-0.8B-UD-Q4_K_XL.gguf
qwen3-reranker-0.6b-q8_0.gguf
```

The reranker starts with:

```text
--embedding --rerank --pooling rank
```

No embedder or vector database is required.

## Run locally

```bash
cp .env.example .env
make doctor
make up
make ready
```

Expected readiness:

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

## Google Calendar

```text
CALENDAR_MODE=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

## Tests

```bash
make check
```

Regression coverage includes routing ambiguity, false scheduling-route escape, scheduling interruption/resume, invalid slot rejection, explicit-confirmation Calendar writes, capability-aware answers and guarded real streaming.
