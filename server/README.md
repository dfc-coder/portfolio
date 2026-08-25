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

Static semantic data is embedded once in memory:

```text
route descriptions  -> embedding vectors, cached
business profile    -> document vectors, cached
```

Each visitor turn requires only a query embedding plus cosine similarity over the cached vectors. This is the standard dense semantic-search pattern: encode the corpus once, encode each query, rank by vector similarity and take the top results.

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

`SemanticRouter` compares the latest visitor turn with three cached semantic route descriptions. During an active meeting task the descriptions become scheduling continuation versus business/general interruption.

Business questions use the same embedding service against the structured business profile. Profile documents are embedded on the first business retrieval and reused for the process lifetime. The query is compared locally with cosine similarity and only the top documents that fit the context budget are sent to the conversational model.

No profile document is pairwise reranked by another language model on every turn.

## Safe real streaming

Business/general answers use llama.cpp streaming end-to-end. `StreamGuard` keeps a small rolling holdback and blocks narrow operational claims such as owner impersonation or claiming an external action completed when it was not verified.

PocketTrace can optionally record router, profile retrieval, context assembly, generation and guard spans without becoming a functional dependency of the agent.

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
