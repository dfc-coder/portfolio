# Portfolio Business Representative

Server-side business representative for a small local Qwen model. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: the conversational Qwen model used for scheduling extraction and grounded response generation.
- `embedding`: Qwen3-Embedding-0.6B used for dense semantic routing and business-profile retrieval.

## Architecture

```text
visitor
  |
  v
SemanticRouter
cached route embeddings + cosine similarity
  |
  +---------------- BUSINESS / GENERAL ----------------+
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
  +---------------- SCHEDULING ------------------------+
                         |
                      Scheduler
                 structured turn extraction
                         |
                  SchedulingMemory
                         |
              explicit human approval
                         |
                    CalendarPort
```

The semantic path intentionally has no cross-encoder reranker, LLM routing judge, topic regex whitelist, vector database, generic tool selector or ReAct loop.

Static semantic data is embedded once during FastAPI startup:

```text
route descriptions  -> embedding vectors, cached
business profile    -> document vectors, cached
```

The application does not finish startup until those vectors are ready. Each visitor turn then requires only a query embedding plus cosine similarity over the cached vectors.

`server/app/agent` contains:

```text
representative.py  thin orchestration
router.py          BUSINESS / SCHEDULING / GENERAL dense routing
context.py         cached dense profile retrieval + prompt assembly
scheduler.py       meeting workflow + hard write invariants
responder.py       grounded knowledge streaming
stream_guard.py    narrow rolling output safety boundary
similarity.py      cosine similarity
```

External boundaries remain separated under `ports/` and `infrastructure/`.

## Scheduling model

Scheduling is represented by facts in `SchedulingMemory` rather than a conversational FSM. Free-form chat text never writes to Calendar. A prepared booking requires explicit approval through the UI before the deterministic booking boundary can run.

A business/general interruption does not clear scheduling memory, so the visitor can resume the meeting later.

## Routing and retrieval

`SemanticRouter` compares the latest visitor turn with cached semantic route descriptions. During an active meeting task the descriptions become scheduling continuation versus business/general interruption.

Business questions use the same embedding service against the structured business profile. Profile document embeddings are computed during startup and reused for the process lifetime. The query is compared locally with cosine similarity and only the top documents that fit the context budget are sent to the conversational model.

No profile document is pairwise reranked by another language model on every turn.

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

Regression coverage includes semantic routing, scheduling interruption/resume, invalid slot rejection, explicit-approval Calendar writes, capability-aware answers, cached profile retrieval and guarded real streaming.
