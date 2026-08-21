# SDD — Belief-Driven Bounded Capability Agent

## 1. Goal

Run a useful portfolio business representative on Qwen3.5-0.8B without asking the small model to own workflow state, side effects, or an unrestricted ReAct loop.

Natural-language interpretation is probabilistic. Applicability, side-effect authorization, tool schemas, and bounded execution are explicit application concerns.

## 2. Runtime topology

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |      |
     |      +-- SemanticRouter -------> Qwen3-Reranker-0.6B
     |      |        \----------------> Qwen3.5-0.8B judge fallback
     |      |
     |      +-- business/general
     |      |      +-- grounded Qwen real stream
     |      |      +-- StreamingOutputGuard
     |      |
     |      +-- scheduling
     |             +-- SchedulingInterpreter
     |             +-- BeliefUpdater
     |             +-- CapabilityRegistry
     |             +-- CapabilitySelector -> reranker / judge
     |             +-- BoundedCapabilityLoop
     |             +-- CapabilitySafetyGate
     |             +-- CapabilityExecutor
     |
     +-- SessionStore
     +-- SlotService
     +-- CalendarPort -------------> Google Calendar
```

The browser never downloads model weights.

## 3. Semantic interpretation

The semantic layer answers what the visitor means, not which concrete tool must execute.

Routing currently produces `domain + relation` with a zero-shot reranker cascade. Scheduling then produces a structured `SchedulingCommand` containing a dialogue act and extracted arguments:

```text
request
inform
select
confirm
cancel
not_applicable
```

The interpreter never emits tool names. A scheduling false positive can therefore return `not_applicable`, causing a second semantic route over only business/general while preserving the active scheduling belief.

The future supervised path is a multi-head classifier for domain/relation/act/OOS. The reranker remains the uncertainty and capability-selection layer; Qwen remains the final ambiguity fallback.

## 4. Belief state instead of conversation stages

Scheduling is represented by facts, not a conversational FSM:

```text
requested_start_date
requested_end_date
offered_slots
selected_slot_id
visitor_name
visitor_email
subject
pending_booking
```

`SchedulingMemory.facts()` derives facts such as:

```text
date_range
offered_slots
selected_slot
details_complete
pending_booking
```

There are no `SCHEDULING_DATES`, `SCHEDULING_SLOT`, or `SCHEDULING_DETAILS` states. Adding a capability does not require adding combinations of conversation states.

`current_focus` remains independent from `active_workflow`, so a business question may interrupt scheduling without destroying dates, slots, or visitor details.

## 5. Declarative capabilities

A capability declares semantic compatibility and applicability:

```text
name
description
domain
accepted dialogue acts
requires_all facts
requires_any facts
forbidden facts
kind: respond | internal | tool
side effect: none | read | write
requires_confirmation
```

Examples:

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

The registry removes impossible actions before semantic selection. One eligible capability executes directly. Several eligible capabilities are ranked by the reranker; Qwen is used only if ranking is ambiguous.

## 6. Bounded capability loop

The action loop is intentionally small:

```text
belief facts
  -> eligible capabilities
  -> select capability
  -> validate safety invariants
  -> execute
  -> observation
  -> continue only when observation requires another step
```

The loop is bounded by `AGENT_MAX_STEPS` and `AGENT_MAX_REPAIRS` (defaults: 3 and 1).

There is no unrestricted Thought/Action/Observation chain and no always-on reflection. Repair is failure-triggered and can only reconsider an applicability/validation failure within the configured bound.

## 7. Safety boundary

Deterministic logic is reserved for invariants that must not depend on semantic confidence:

- a selected slot must have been offered in this session;
- a write must pass its confirmation policy;
- a pending booking must contain a valid email;
- a Calendar write must reference the selected offered slot;
- execution is bounded;
- successful booking text is emitted only after the Calendar API succeeds.

These are safety constraints, not intent-routing rules.

`calendar.create_booking` is not exposed merely because the visitor says something semantically similar to confirmation. It becomes eligible only when the pending-booking facts exist and the deterministic explicit-confirmation policy accepts the latest message.

## 8. Capability execution

`CapabilityExecutor` is a handler registry. It does not decide which action should happen.

Current handlers include:

- ask for dates;
- show/remind offered slots;
- search availability;
- select an offered slot;
- ask for missing visitor details;
- prepare a non-destructive pending booking;
- remind that confirmation is required;
- create the booking through `CalendarPort`;
- cancel and clear scheduling belief.

External tools remain behind ports. Internal state transformations and external calls share the capability abstraction but have explicit `kind` and `side_effect` metadata.

## 9. Safe real streaming

Business/general responses use llama.cpp `stream=true` end-to-end.

```text
Qwen token stream
      -> rolling safety holdback
      -> FastAPI SSE
      -> browser ReadableStream
```

No completed response is replayed with sleeps or a typewriter animation. The rolling guard blocks restricted operational claims before they cross the SSE boundary.

Scheduling/tool responses are deterministic and emitted atomically. Calendar side effects are unreachable from the informational renderer.

## 10. Context and inference

The semantic router sees only compact conversation state: current focus, active workflow, scheduling facts, offered slot IDs, the last assistant message, and the latest visitor message.

The scheduling interpreter sees compact scheduling belief plus current time/timezone. It extracts meaning and arguments but does not plan tools.

Grounded business rendering receives recent turns plus `BUSINESS_CONTEXT`. Thinking remains disabled. llama.cpp prompt caching remains enabled.

## 11. Package boundaries

```text
app/api             transport and SSE
app/domain          belief, semantics, capabilities, observations
app/agent           interpretation, routing, belief update, capability selection/loop, safety, rendering
app/scheduling      date policy and availability calculation
app/ports           external capability protocols
app/infrastructure  concrete llama.cpp, reranker, Calendar and session adapters
app/bootstrap.py    dependency composition
```

The former conversation FSM, action planner, and monolithic action executor are intentionally removed.
