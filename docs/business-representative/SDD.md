# SDD — Bounded Reflective ReAct Business Representative

## 1. Goal

Run a useful portfolio business representative on Qwen3.5-0.8B without asking the small model to own workflow state, side effects or unrestricted reasoning.

The model is a bounded linguistic component. Python owns business state and correctness boundaries.

## 2. Runtime topology

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |     +-- ConversationFSM
     |     +-- StructuredPlanner ----> llama.cpp / Qwen3.5-0.8B
     |     +-- AgentVerifier
     |     +-- ActionExecutor
     |     +-- HybridRenderer -------> llama.cpp / Qwen3.5-0.8B
     |
     +-- SessionStore
     +-- SlotService
     +-- CalendarPort -------------> Google Calendar
```

## 3. Agent contract

The orchestrator runs at most `AGENT_MAX_STEPS` actions per visitor turn and at most `AGENT_MAX_REPAIRS` repair calls.

```text
state
  -> plan (constrained JSON)
  -> deterministic verification
  -> execute
  -> observation
  -> state transition
  -> next step only when explicitly required
```

There is no unrestricted chain-of-thought loop and no model-controlled destructive tool.

## 4. Conversation FSM

```text
BUSINESS
SCHEDULING_DATES
SCHEDULING_SLOT
SCHEDULING_DETAILS
SCHEDULING_CONFIRMATION
COMPLETE
```

The state determines which actions are legal. Scheduling intent regex is used only to enter the workflow from `BUSINESS`; it is not re-run as the authority for every follow-up.

Structured session state stores:

- requested date range;
- offered slots keyed as `S1`, `S2`, ...;
- selected slot id;
- visitor name;
- visitor email;
- meeting subject;
- pending booking;
- last successful booking id.

## 5. Planner

The planner receives only:

- current time and timezone;
- current FSM stage;
- allowed actions;
- structured scheduling state;
- at most four recent turns;
- latest observation;
- current visitor message.

It returns the Pydantic `Plan` schema. llama.cpp JSON-schema response format is requested first; a JSON-object fallback is used only if the server does not support that response format. Pydantic validation and `AgentVerifier` remain authoritative.

## 6. Executor

`ActionExecutor` contains no planning logic. It executes one validated action:

- ask for dates;
- get availability;
- select a previously offered slot;
- collect meeting details;
- prepare a non-destructive pending booking;
- cancel workflow state.

Google Calendar writes are not executor actions.

## 7. Triggered reflection

Reflection is failure-triggered, not always-on.

```text
plan
  -> verify
       -> pass: execute
       -> fail: one repair call
                   -> verify again
                        -> pass: execute
                        -> fail: safe deterministic fallback
```

Business rendering uses a second verifier for critical invariants such as owner impersonation or claiming a booking without Calendar success.

## 8. Rendering

Scheduling responses are deterministic templates so slot times, missing fields, confirmation state and Calendar outcomes cannot be rewritten incorrectly by the model.

Qwen is used for ordinary business Q&A because language quality matters there. Owner-specific claims remain bounded to `business-profile.json`.

## 9. Side-effect safety

A Calendar write can occur only when:

1. availability previously produced the slot;
2. the slot was selected into session state;
3. required visitor details were collected;
4. a pending booking exists;
5. the visitor explicitly confirms;
6. Google Calendar accepts the write.

Failure never becomes a success claim. A transient Calendar write failure leaves the pending booking available for an explicit retry.

## 10. Context and latency

Default raw history retention is reduced from 12 to 8 turns. The planner consumes at most four recent turns plus structured state. llama.cpp prompt caching remains enabled and the model stays resident behind one inference slot.

Planner, renderer and repair have independent sampling profiles. Thinking is disabled.

## 11. Package boundaries

```text
app/api             transport only
app/domain          dependency-free business types
app/agent           application orchestration
app/scheduling      deterministic scheduling rules
app/ports           external capability protocols
app/infrastructure  concrete adapters
app/bootstrap.py    dependency composition
```

Compatibility modules at the old top-level import paths contain exports only and no business logic.
