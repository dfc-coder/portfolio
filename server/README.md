# Portfolio Business Representative

Server-side business representative for a small local Qwen model. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: conversational Qwen used for grounded responses and ambiguous scheduling continuation.
- `embedding`: Qwen3-Embedding-0.6B used for portfolio knowledge retrieval.

## Architecture

```text
visitor
  |
  v
Scheduling admission
  | explicit meeting request or active workflow
  +---------------- yes ----------------> Scheduler
  |                                      |
  |                               SchedulingMemory
  |                                      |
  |                            explicit human approval
  |                                      |
  |                                 CalendarPort
  |
  +---------------- no -----------------+
                                           |
                                           v
                                  dense profile retrieval
                                  cached document vectors
                                           |
                               score >= relevance threshold?
                                  |                 |
                                 yes                no
                                  |                 |
                             BUSINESS            GENERAL
                                  \                 /
                                   \               /
                                      Responder
                                         |
                                     StreamGuard
                                         |
                                        SSE
```

There is no semantic intent router for portfolio knowledge. The structured profile itself defines the knowledge domain. Every non-scheduling turn performs one query embedding against the cached profile-document vectors. Relevant chunks are injected into the prompt; if no chunk meets the global relevance threshold, the same responder answers without portfolio context.

This follows the retrieval-first pattern used by production RAG assistants: retrieve the configured knowledge source, apply a similarity/relevance threshold, then give only the surviving context to the LLM. It avoids maintaining a second semantic taxonomy of sample user phrases.

## Why BUSINESS has no utterance list

`business-profile.json` is the source of truth for portfolio facts:

```text
owner
positioning
experience.*
professional_experience.*
skills.*
services.*
projects.*
education.*
certifications.*
languages.*
business.*
representative.capabilities
```

Those records are transformed into small documents and embedded once during startup.

At runtime:

```text
latest visitor message
        |
        v
one query embedding
        |
        v
cosine against cached portfolio vectors
        |
        +-- relevant documents --> grounded portfolio response
        |
        +-- no relevant documents --> general response
```

Adding a project, skill or experience to the profile makes it retrievable automatically. No routing examples need to be added.

The relevance boundary is one configuration value:

```env
KNOWLEDGE_RELEVANCE_THRESHOLD=0.50
```

`PocketTrace` records the top retrieval score, threshold and selected document IDs so this boundary is observable without adding routing logic.

## Scheduling is a separate operational boundary

Scheduling is not treated as portfolio knowledge. A new scheduling workflow is admitted only for an explicit meeting request. Once a scheduling workflow is active, the existing deterministic-first parser can interpret dates, slots, contact details and cancellation; its small semantic fallback is available only inside that already-active workflow.

Free-form chat never writes to Calendar. A prepared booking requires explicit human approval through the UI before the deterministic booking boundary can run.

## Code ownership

```text
representative.py  orchestration + scheduling admission
knowledge.py       profile documents + dense relevance gate
context.py         prompt + runtime facts
scheduler.py       meeting workflow + hard write invariants
responder.py       retrieval-driven response streaming
stream_guard.py    narrow output safety boundary
```

There is no cross-encoder reranker, LLM routing judge, business-topic regex whitelist, vector database, ReAct loop or separate semantic-router dependency.

## Startup and latency

Profile document embeddings are computed once during FastAPI startup and reused for the process lifetime.

Each normal non-scheduling turn requires:

```text
1 query embedding
+ local cosine scoring
+ Qwen response generation
```

No second routing embedding is performed.

## Optional PocketTrace observability

PocketTrace is opt-in:

```env
POCKETTRACE_ENABLED=false
```

With `false` (the default), `PocketTraceRecorder` is not instantiated and the agent makes no PocketTrace HTTP calls.

For local diagnostics:

```env
POCKETTRACE_ENABLED=true
POCKETTRACE_URL=http://host.containers.internal:4319
POCKETTRACE_TIMEOUT_SECONDS=1.0
```

## Required models

Place both GGUF files in `LLAMA_MODELS_DIR`:

```text
<your Qwen3.5 conversational GGUF>
Qwen3-Embedding-0.6B-Q8_0.gguf
```

The embedding server starts with:

```text
--embedding --pooling last
```

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

Regression coverage includes cached profile embeddings, relevance threshold gating, experience retrieval, general no-match, scheduling interruption/resume, explicit admission for new scheduling workflows, invalid slot rejection, explicit-approval Calendar writes and guarded streaming.
