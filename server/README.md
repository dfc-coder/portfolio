# Portfolio Business Representative

Server-side portfolio representative for a small local Qwen model. The browser never downloads model weights. Two llama.cpp services stay resident:

- `llama`: conversational Qwen used for scheduling extraction and response generation.
- `embedding`: Qwen3-Embedding-0.6B used for semantic domain routing and portfolio retrieval.

## Architecture

```text
visitor
  |
  v
BusinessRepresentative
  |
  +-- CONVERSATION --------------------> Responder -> StreamGuard -> SSE
  |
  +-- PORTFOLIO ---> PortfolioSearch --> Responder -> StreamGuard -> SSE
  |                    |
  |                    +--> profile knowledge + cached embeddings
  |
  +-- SCHEDULING ---> Scheduler
                         |
                         +--> SlotService --> Calendar

explicit UI approval
  |
  v
BookingApproval --> Calendar --> Google Calendar
```

The server intentionally has no ToolRegistry, ToolExecutor, BaseTool, generic ToolResult, planner, ReAct loop, agent graph, cross-encoder reranker or LLM routing judge.

## Explicit capabilities

`BusinessRepresentative` is deliberately small and explicit:

```text
SCHEDULING -> Scheduler
PORTFOLIO  -> PortfolioSearch -> Responder
otherwise  -> Responder
```

`SemanticRouter` returns only one domain:

```text
CONVERSATION
PORTFOLIO
SCHEDULING
```

It does not select Python functions or tool names.

`PortfolioSearch` exposes a stable business API:

```python
search(query: str) -> SearchResult
```

`SearchResult` contains concrete `Fact` values with `text` and `source`. The current backend flattens `business-profile.json`, embeds documents once, and performs local cosine retrieval. A future vector database or document backend can replace that implementation without changing the capability API.

`Responder` receives evidence. It does not own retrieval and does not know where facts came from.

## Routing and retrieval

Static route descriptions and portfolio documents are embedded once and cached. Each visitor turn uses a query embedding plus cosine similarity against cached vectors.

For short portfolio follow-ups, the search query may include recent visitor turns. Previous assistant text is deliberately excluded so generated text cannot become retrieval evidence.

`PORTFOLIO_MIN_SCORE` controls the minimum similarity required for a retrieved document to become supported evidence. If no fact survives, the response prompt exposes `RELEVANT_KNOWLEDGE=<none>` and requires abstention rather than invention.

## Scheduling and Calendar

Scheduling is represented by facts in `SchedulingMemory` rather than a conversational FSM.

`Scheduler` prepares scheduling state and pending bookings but does not receive Calendar directly and cannot write events. Availability is read through `SlotService` and the scheduling-owned `Calendar` boundary.

A free-form message such as "sí, confirmo" cannot authorize a write. A prepared booking crosses the side-effect boundary only through the explicit UI approval endpoint handled by `BookingApproval`, which validates the pending booking before calling Calendar.

Portfolio or conversational interruptions do not clear active scheduling memory.

## Safe streaming

`Responder` streams from llama.cpp end-to-end. `StreamGuard` remains a narrow output safety boundary for unverified operational claims, but authorization comes from control flow rather than generated text filtering.

## Package layout

```text
app/api                       HTTP, SSE and approval endpoints
app/agent                     representative, router, scheduler, responder, guard
app/portfolio                 PortfolioSearch and concrete result types
app/domain                    conversation/profile/routing/scheduling data
app/scheduling                Calendar boundary, policy, slots, approval
app/infrastructure/knowledge  current profile retrieval backend
app/infrastructure            llama.cpp, embeddings, Calendar gateways, tracing, config, sessions
app/bootstrap.py              dependency composition
```

There is intentionally no `tools/` package. Native function calling or MCP can be introduced later as thin adapters over the explicit capabilities.

## Optional PocketTrace observability

PocketTrace is optional and never becomes a functional dependency.

```env
POCKETTRACE_ENABLED=false
```

Enable it explicitly for local diagnostics:

```env
POCKETTRACE_ENABLED=true
POCKETTRACE_URL=http://host.containers.internal:4319
POCKETTRACE_TIMEOUT_SECONDS=1.0
```

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

Regression coverage includes domain-only routing, explicit portfolio retrieval, evidence-only response context, scheduling interruption/resume, explicit-approval Calendar writes and guarded real streaming.
