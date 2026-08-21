# SDD — Portfolio Business Representative

## Goal

Run a useful server-side representative on Qwen3.5-0.8B with real streaming, reliable Calendar writes and a codebase small enough to reason about.

The design intentionally avoids a conversational FSM, generic capability registry and generic ReAct loop until the product actually needs them.

## Runtime

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |      +-- SemanticRouter ------> Qwen3-Reranker-0.6B
     |      |                         + Qwen 0.8B ambiguity fallback
     |      +-- Scheduler -----------> Qwen 0.8B structured extraction
     |      |                         + CalendarPort
     |      +-- Responder -----------> Qwen 0.8B real stream
     |                                + StreamGuard
     |
     +-- SessionStore
     +-- SlotService
     +-- CalendarPort -------------> Google Calendar
```

## Agent boundary

`BusinessRepresentative` only orchestrates: append the visitor turn, route, delegate, and persist the assistant turn. It contains no workflow rules and no tool execution logic.

## Routing

`SemanticRouter` evaluates business, scheduling and general. Qwen3-Reranker handles the normal zero-shot route. Qwen3.5-0.8B is used only when the reranker score/margin is ambiguous.

During an active scheduling task, business/general routes are interruptions and scheduling is continuation. Scheduling memory is preserved across interruptions.

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

`Scheduler` performs one structured interpretation of the latest scheduling turn, updates this memory, and directly performs the next necessary meeting operation.

There is no `DATES -> SLOT -> DETAILS -> CONFIRMATION` state machine.

The only external Calendar operations are read availability and create a prepared booking.

## Write safety

Calendar creation is authorized only when hard invariants hold: a pending booking exists, the selected slot was previously offered, visitor email is valid, the latest visitor message satisfies explicit-confirmation policy, and the Calendar API accepts the write.

The free-form responder cannot execute Calendar writes.

## False scheduling routes

A routed scheduling message is interpreted again inside the narrow scheduling context. If it is actually a professional/general question, `Scheduler` returns `not_applicable` and the representative reroutes only across business/general.

This protects active meeting memory from false positives such as "¿Podés usar herramientas?".

## Grounded real streaming

`Responder` receives `BUSINESS_CONTEXT`, `AGENT_CAPABILITIES`, current time, focus and workflow summary. It streams directly from llama.cpp.

`StreamGuard` keeps a small rolling holdback and blocks only narrow operational claims such as impersonating Diego or claiming an unverified completed Calendar action.

Capability descriptions remain allowed. "Puedo agendar una reunión después de que confirmes" is valid; "la reunión ya quedó agendada" is reserved for the successful deterministic booking path.

## Package boundaries

```text
app/api             HTTP + SSE
app/agent           representative, router, scheduler, responder, stream guard
app/domain          session/profile/routing/scheduling data
app/scheduling      date policy + availability calculation
app/ports           LLM, reranker, calendar, sessions
app/infrastructure  llama.cpp, Google Calendar, config, sessions
app/bootstrap.py    dependency composition
```

## Future evolution

A trained intent classifier is deferred until reviewed production examples exist. If the number of independent tools grows enough to justify semantic tool retrieval, the existing reranker can be reused then rather than maintaining speculative abstractions today.
