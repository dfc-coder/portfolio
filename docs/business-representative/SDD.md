# SDD — Portfolio Business Representative

## Goal

Run a useful server-side representative on a small local Qwen model with real streaming, grounded portfolio answers and reliable Calendar writes while keeping the runtime easy to reason about.

## Runtime

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |      |
     |      +-- scheduling admission
     |      |       |
     |      |       +-- Scheduler --> CalendarPort / HITL approval
     |      |
     |      +-- Responder
     |              |
     |              +-- ProfileRetriever --> Qwen3-Embedding-0.6B
     |              |                     cached document vectors
     |              +-- Qwen real stream
     |              +-- StreamGuard
     |
     +-- SessionStore
     +-- SlotService
     +-- CalendarPort -------------> Google Calendar
```

## Knowledge boundary

There is no semantic intent router for `BUSINESS`.

`business-profile.json` is flattened into retrievable documents. Their embeddings are computed once at startup. Every non-scheduling visitor turn uses the latest message as a single retrieval query.

```text
latest message
    |
    v
query embedding
    |
    v
cosine against cached profile documents
    |
    +-- score >= threshold --> BUSINESS + retrieved knowledge
    |
    +-- no qualifying document --> GENERAL
```

This makes the data source itself define the portfolio domain. Adding a skill, project or experience changes the retrievable knowledge without requiring a second list of routing examples.

The global boundary is `KNOWLEDGE_RELEVANCE_THRESHOLD`; PocketTrace records the top score and selected documents.

## Scheduling boundary

Scheduling is operational, not a knowledge topic.

A new workflow is admitted only by an explicit meeting request. A bare date, email or unrelated question cannot start scheduling. Once `ActiveWorkflow.SCHEDULING` exists, the deterministic-first parser handles dates, slots, contact details and cancellation; its semantic fallback is limited to ambiguous continuations inside that active workflow.

Free-form text never writes to Calendar. A prepared booking crosses the write boundary only after explicit human approval in the UI.

Business/general interruptions do not clear `SchedulingMemory`.

## Prompt boundary

`ContextAssembler` owns one base prompt. It always includes verified runtime state. Portfolio owner identity and portfolio facts are added only when retrieval produced qualifying documents.

The model therefore receives:

```text
base instructions
+ verified runtime facts
+ optional retrieved portfolio knowledge
+ short visible conversation history
```

There are no separate GENERAL/BUSINESS prompt copies.

## Observability

PocketTrace is optional and fail-open. Useful spans are:

```text
scheduler
profile_retrieval
context_assembler
qwen_generation
stream_guard
```

`profile_retrieval` includes the query, threshold, top score and selected document IDs/content.

## Package boundaries

```text
app/api             HTTP + SSE
app/agent           representative, knowledge, context, scheduler, responder, guard
app/domain          session/profile/routing/scheduling data
app/scheduling      operational admission + date policy + availability calculation
app/ports           LLM, embeddings, calendar, sessions
app/infrastructure  llama.cpp, embeddings, PocketTrace, Calendar, config, sessions
app/bootstrap.py    dependency composition
```
