# Portfolio Business Representative

Server-side **bounded capability agent** optimized for Qwen3.5-0.8B. The browser never downloads model weights. Two small llama.cpp services stay resident:

- `llama`: Qwen3.5-0.8B for semantic extraction, low-confidence routing/capability fallback and grounded response generation.
- `reranker`: Qwen3-Reranker-0.6B for zero-shot routing today and semantic capability selection as the tool catalog grows.

## Architecture

```text
visitor + compact context
        |
        v
semantic router
reranker -> Qwen judge on ambiguity
        |
        +---------------- business/general ----------------+
        |                                                  |
        |                                           grounded Qwen
        |                                              real stream
        |                                                  |
        |                                           streaming guard
        |                                                  |
        |                                                 SSE
        |
        +---------------- scheduling ----------------------+
                           |
                  scheduling interpreter
                 meaning + extracted args
                    (never tool names)
                           |
                           v
                      belief updater
                    facts, not stages
                           |
                           v
                   capability registry
               declarative preconditions
                           |
                    eligible actions
                           |
               1 -> direct / N -> reranker
                           |
                           v
                  bounded capability loop
                 max steps / max repairs
                           |
                           v
                       safety gate
             schema + invariants + confirmation
                           |
                           v
                  capability executor
                Calendar / internal action
                           |
                           v
                     observation
                           |
                    deterministic text
```

There is no conversational scheduling FSM. `SessionState` holds a `SchedulingMemory` with facts such as requested dates, offered slots, selected slot, visitor details and pending booking. Capabilities declare which facts they require or forbid. Adding a capability does not require adding combinations of conversation stages.

The remaining deterministic rules are deliberate safety invariants: a selected slot must have been offered, writes require explicit confirmation, tool arguments must be valid, and the loop is bounded. These are not semantic intent rules.

`SessionState.current_focus` is independent from `SessionState.active_workflow`. A visitor can interrupt an active scheduling task with a business/general question and later resume the same scheduling belief.

```text
app/
  api/                     HTTP + SSE boundary
  agent/
    semantic_router.py     domain/relation cascade
    interpreter.py         scheduling act + argument extraction
    belief.py              fact updates
    capability_registry.py declarative applicability
    selector.py            reranker + Qwen capability fallback
    loop.py                bounded execution/repair
    safety.py              deterministic side-effect invariants
    capability_executor.py handler registry
    renderer.py            deterministic workflow rendering + LLM stream
    streaming_guard.py     rolling output safety holdback
    representative.py      thin orchestrator
  domain/
    conversation.py        belief/session state
    semantics.py           dialogue acts and commands
    capabilities.py        capability metadata
  scheduling/              date policy + availability calculation
  ports/                   LLM, reranker, calendar, sessions
  infrastructure/          llama.cpp, Google Calendar, config, sessions
  bootstrap.py             composition root
```

## Semantic routing and future classifier

The current router remains dataset-free:

```text
reranker
   |
   +-- confident --> domain + relation
   |
   +-- ambiguous --> Qwen 0.8B constrained judge
```

With no active workflow the candidates are `business`, `scheduling`, and `general`. During scheduling they become `business/general interrupt` versus `scheduling continue`. If the scheduling interpreter determines that a routed message is actually `not_applicable`, the system reroutes across only business/general candidates and preserves scheduling facts.

The intended evolution once reviewed production examples exist is:

```text
multi-head classifier (domain / relation / act / OOS)
        |
   low confidence
        v
     reranker
        |
   still ambiguous
        v
   Qwen judge
```

The reranker is therefore not discarded when a classifier is introduced; it becomes the uncertainty/tool-selection layer.

## Capability model

Capabilities are declarations rather than conversation-state branches. Examples:

```text
calendar.search_availability
  act: request | inform
  requires: date_range
  side_effect: read

scheduling.select_slot
  act: select
  requires: offered_slots + slot_reference
  side_effect: none

calendar.create_booking
  act: confirm
  requires: pending_booking + explicit_confirmation
  side_effect: write
```

The capability registry filters impossible actions before semantic selection. When only one capability is eligible it executes directly. If several are eligible, Qwen3-Reranker ranks only that reduced set; the 0.8B model is used only as an ambiguity fallback.

## Bounded reflection/tool loop

The loop is intentionally small:

```text
resolve eligible capabilities
        |
select capability
        |
validate invariants
        |
execute
        |
observation
        |
continue only when required
```

Defaults remain `AGENT_MAX_STEPS=3` and `AGENT_MAX_REPAIRS=1`. Reflection is triggered only by a failed applicability/validation path; there is no unbounded free-form Thought/Action loop.

Calendar writes are never inferred from natural language alone. `calendar.create_booking` becomes eligible only when a pending booking exists and the deterministic confirmation policy accepts the latest visitor message. Successful booking text is emitted only after the Calendar call succeeds.

## Safe real streaming

Business/general knowledge answers use llama.cpp with `stream=true` end-to-end. The backend does not wait for a complete answer and does not replay completed text with artificial delays.

A small rolling character holdback sits between the model stream and SSE. It exists only to prevent restricted operational claims from crossing the HTTP boundary, including owner impersonation and generated claims that a meeting was booked or an invitation was sent. It adds no timer or typewriter animation.

Owner-specific claims are grounded by prompt contract against `BUSINESS_CONTEXT`. Scheduling/tool results are deterministic Python text and are emitted atomically.

## Required models

Place both GGUF files in `LLAMA_MODELS_DIR` (defaults to `server/models`):

```text
Qwen3.5-0.8B-UD-Q4_K_XL.gguf
qwen3-reranker-0.6b-q8_0.gguf
```

The main model filename is configurable with `LLAMA_MODEL_FILE`; the reranker is configurable with `RERANKER_MODEL_FILE`.

The reranker service starts with:

```text
--embedding --rerank --pooling rank
```

No embedder or vector database is required for the current router/capability catalog.

## Run locally

```bash
cp .env.example .env
make doctor
make up
make ready
```

Expected readiness:

```json
{"status":"ok","llama":"ready","reranker":"ready"}
```

Useful commands:

```bash
make logs
make logs-reranker
make models
make check
```

For production, pin `LLAMA_IMAGE` to a known llama.cpp tag or digest rather than a floating tag.

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

Coverage includes routing ambiguity, false scheduling-route escape, belief preservation across interruptions, declarative capability eligibility, guarded real streaming, slot validation, bounded scheduling execution, and explicit-confirmation Calendar writes.
