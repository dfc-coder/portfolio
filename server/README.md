# Portfolio Knowledge Agent

Server-side portfolio assistant for a small local Qwen model. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: conversational Qwen used for grounded responses.
- `embedding`: Qwen3-Embedding-0.6B used for portfolio knowledge retrieval.

## Architecture

```text
visitor
  |
  v
dense profile retrieval
cached document vectors
  |
score >= relevance threshold?
  |                 |
 yes                no
  |                 |
BUSINESS          GENERAL
  \                 /
   \               /
      Responder
         |
     StreamGuard
         |
        SSE
```

There is no semantic intent router for portfolio knowledge. The structured profile itself defines the knowledge domain. Every turn performs one query embedding against the cached profile-document vectors. Relevant chunks are injected into the prompt; if no chunk meets the relevance threshold, the same responder answers without portfolio context.

## Knowledge source

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
faq.*
```

Those records are transformed into small natural-language documents and embedded once during startup.

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
KNOWLEDGE_RELEVANCE_THRESHOLD=0.25
```

`PocketTrace` records the top retrieval score, threshold and selected documents so the boundary is observable without adding routing logic.

## Code ownership

```text
representative.py  thin conversation orchestration
knowledge.py       profile documents + dense relevance gate
context.py         prompt + verified runtime facts
responder.py       retrieval-driven response streaming
stream_guard.py    narrow output safety boundary
```

There is no cross-encoder reranker, LLM routing judge, business-topic regex whitelist, vector database, ReAct loop, scheduling workflow or Calendar integration.

## Startup and latency

Profile document embeddings are computed once during FastAPI startup and reused for the process lifetime.

Each turn requires:

```text
1 query embedding
+ local cosine scoring
+ Qwen response generation
```

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

## Tests

```bash
make check
```

Regression coverage includes cached profile embeddings, relevance threshold gating, experience retrieval, general no-match, knowledge-only architecture and guarded streaming.
