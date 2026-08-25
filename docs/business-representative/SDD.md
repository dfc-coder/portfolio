# SDD — Portfolio Business Representative

## Goal

Run a useful server-side representative on a small local Qwen model with real streaming, reliable Calendar writes and a codebase small enough to reason about.

The design intentionally avoids a conversational FSM, generic capability registry, generic ReAct loop, cross-encoder reranker and LLM routing judge.

## Runtime

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |      +-- SemanticRouter ------> Qwen3-Embedding-0.6B
     |      |                         cached route vectors + cosine
     |      +-- Scheduler -----------> Qwen structured extraction
     |      |                         + CalendarPort / HITL approval
     |      +-- Responder -----------> cached profile vectors
     |                                + Qwen real stream
     |                                + StreamGuard
     |
     +-- SessionStore
     +-- SlotService
     +-- CalendarPort -------------> Google Calendar
```

## Agent boundary

`BusinessRepresentative` only orchestrates: append the visitor turn, route, delegate, and persist the assistant turn. It contains no workflow rules and no tool execution logic.

## Semantic routing

`SemanticRouter` keeps natural-language descriptions for business, scheduling and general intent. Their embeddings are computed once and cached. Each visitor turn requires one query embedding and local cosine similarity against those cached vectors.

During an active scheduling task, the descriptions become business interruption, scheduling continuation and general interruption. Scheduling memory is preserved across interruptions.

There is no topic regex whitelist, reranker threshold cascade or LLM judge.

## Business-profile retrieval

`business-profile.json` is flattened into small structural documents such as `projects.3`, `experience.0` and `skills`. Document embeddings are computed once on the first business retrieval and then cached for the process lifetime.

For each business turn:

```text
recent visitor context
       |
       v
query embedding
       |
       v
cosine similarity against cached profile vectors
       |
       v
top documents within context budget
       |
       v
Responder
```

The retrieval service never pairwise-scores every profile document with a cross-encoder on each request.

## Scheduling

Scheduling state is data, not a conversation stage:

```text
SchedulingMemory
- requested date range
- offered slots
- selected slot id
- visitor name
- visitor email
- subject
- pending booking
```

`Scheduler` performs structured interpretation of scheduling turns and updates this memory. Free-form text never writes to Calendar. A prepared booking crosses the write boundary only after explicit human approval in the UI.

A business/general interruption does not clear `SchedulingMemory`.

## False scheduling routes

A message routed to scheduling is interpreted again inside the narrow scheduling context. If it is not applicable, `Scheduler` returns `not_applicable` and the representative reroutes only between business and general without destroying meeting memory.

## Grounded real streaming

`Responder` receives retrieved owner facts, agent capabilities, current time, focus and workflow summary and streams directly from llama.cpp.

`StreamGuard` keeps a small rolling holdback and blocks narrow operational claims such as impersonating Diego or claiming an unverified completed Calendar action.

## Observability

PocketTrace is optional and fail-open. It records `router`, `profile_retrieval`, `context_assembler`, `qwen_generation`, `stream_guard` and scheduling spans without participating in decisions.

## Package boundaries

```text
app/api             HTTP + SSE
app/agent           representative, router, context, scheduler, responder, guard
app/domain          session/profile/routing/scheduling data
app/scheduling      date policy + availability calculation
app/ports           LLM, embeddings, calendar, sessions
app/infrastructure  llama.cpp, embeddings, PocketTrace, Calendar, config, sessions
app/bootstrap.py    dependency composition
```
