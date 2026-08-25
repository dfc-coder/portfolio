# Portfolio Business Representative

Server-side business representative for a small local Qwen model. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: the conversational Qwen model used for scheduling extraction and grounded response generation.
- `embedding`: Qwen3-Embedding-0.6B used for semantic routing and business-profile retrieval.

## Architecture

```text
visitor
  |
  v
Aurelio semantic-router
positive routes: BUSINESS / SCHEDULING
threshold miss or ambiguity -> GENERAL
  |
  +---------------- BUSINESS --------------------------+
  |                                                    |
  |                                         dense profile retrieval
  |                                     cached document embeddings
  |                                                    |
  |                                                Responder
  |                                                    |
  |                                                StreamGuard
  |                                                    |
  |                                                   SSE
  |
  +----------- SCHEDULING CANDIDATE ------------------+
  |                      |                             |
  |                  admission                         |
  |            deterministic evidence?                 |
  |               |              |                     |
  |              yes             no -------------------+
  |               |                                    |
  |           Scheduler                               GENERAL
  |               |
  |        SchedulingMemory
  |               |
  |    explicit human approval
  |               |
  |          CalendarPort
  |
  +---------------- NO MATCH -------------------------> GENERAL
```

The semantic path intentionally has no cross-encoder reranker, LLM routing judge, topic regex whitelist, vector database, generic tool selector or ReAct loop.

Static semantic data is embedded once during FastAPI startup:

```text
business route utterances     -> vectors in semantic-router LocalIndex
scheduling route utterances   -> vectors in semantic-router LocalIndex
business profile              -> document vectors, cached
```

The application does not finish startup until those vectors are ready. Each normal visitor turn then requires one query embedding plus local in-memory similarity scoring.

`server/app/agent` contains:

```text
representative.py  thin orchestration
router.py          open-set semantic-router adapter
context.py         cached dense profile retrieval + prompt assembly
scheduler.py       meeting workflow + hard write invariants
responder.py       grounded knowledge streaming
stream_guard.py    narrow rolling output safety boundary
```

`server/app/infrastructure/embeddings/semantic_router.py` adapts the existing llama.cpp `EmbeddingPort` to semantic-router's async asymmetric encoder interface. No second embedding model is loaded.

## Open-set routing

Only `business` and `scheduling` are positive routes on a new conversation. `GENERAL` is the abstention/default path; it is not an indexed semantic route.

```text
business match       -> BUSINESS
scheduling match     -> SCHEDULING candidate
no threshold match   -> GENERAL
ambiguous top routes -> GENERAL
```

Routes contain multiple Spanish and English utterances. Aurelio semantic-router applies the per-route score threshold; the adapter also requires a minimum margin when more than one positive route passes.

Thresholds are configuration, not runtime learning:

```env
ROUTER_BUSINESS_THRESHOLD=0.55
ROUTER_SCHEDULING_THRESHOLD=0.58
ROUTER_CONTINUATION_THRESHOLD=0.50
ROUTER_MIN_MARGIN=0.05
```

During an active meeting task a second static route layer distinguishes `scheduling_continue` from `business_interrupt`; a miss becomes a general interruption and the existing meeting state remains intact.

## Scheduling admission

Scheduling is represented by facts in `SchedulingMemory` rather than a conversational FSM. Free-form chat text never writes to Calendar. A prepared booking requires explicit approval through the UI before the deterministic booking boundary can run.

A semantic scheduling match is only a candidate. For a new conversation, the deterministic `SchedulingTurnParser` must find actual scheduling evidence before a workflow can start. Its small LLM semantic fallback is available only after `ActiveWorkflow.SCHEDULING` already exists, where it can interpret ambiguous continuations without gaining authority to create a workflow.

This makes the operational boundary fail closed: a routing false positive cannot by itself start scheduling.

## Business retrieval

Business questions continue to use the same embedding service against the structured business profile. Profile document embeddings are computed during startup and reused for the process lifetime. The query is compared locally with cosine similarity and only the top documents that fit the context budget are sent to the conversational model.

Semantic-router is used only for intent selection; it does not replace profile retrieval.

## Safe real streaming

Business/general answers use llama.cpp streaming end-to-end. `StreamGuard` keeps a small rolling holdback and blocks narrow operational claims such as owner impersonation or claiming an external action completed when it was not verified.

## Optional PocketTrace observability

PocketTrace is strictly optional and never becomes a functional dependency of the agent.

```env
POCKETTRACE_ENABLED=false
```

With `POCKETTRACE_ENABLED=false` (the default), `PocketTraceRecorder` is not instantiated: the agent does not create trace snapshots and does not make HTTP calls to PocketTrace.

Enable it explicitly for local development when trace-level diagnostics are needed:

```env
POCKETTRACE_ENABLED=true
POCKETTRACE_URL=http://host.containers.internal:4319
POCKETTRACE_TIMEOUT_SECONDS=1.0
```

This can remain `false` in production or in any environment where trace payload capture is not desired.

## Required models

Place both GGUF files in `LLAMA_MODELS_DIR` (defaults to `server/models`):

```text
<your Qwen3.5 conversational GGUF>
Qwen3-Embedding-0.6B-Q8_0.gguf
```

The embedding server starts with:

```text
--embedding --pooling last
```

No Python ML runtime or vector database is required; both models run through llama.cpp.

## Run locally

```bash
cp .env.example .env
make doctor
make up
make ready
```

Expected readiness:

```json
{"status":"ok","llama":"ready","embedding":"ready"}
```

Useful commands:

```bash
make logs
make logs-embedding
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

Regression coverage includes open-set routing/no-match, ambiguity fallback, scheduling interruption/resume, prevention of semantic-only scheduling startup, invalid slot rejection, explicit-approval Calendar writes, capability-aware answers, cached profile retrieval and guarded real streaming.
