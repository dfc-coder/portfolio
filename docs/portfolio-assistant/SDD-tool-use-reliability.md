# SDD — Tool-use reliability

Status: Implemented, pending live regression validation

Branch: `feat/agent-live-eval`

## 1. Problem

The live traces separated four different failure modes that had previously been conflated:

1. deciding whether any tool is needed;
2. selecting the correct capability;
3. extracting the correct arguments;
4. producing a final answer consistent with the tool result.

The latest traced smoke after reducing the public tool surface to three operations still exposed two structural problems:

```text
general joke
-> search_portfolio twice

explicit date
-> resolve_datetime(base=now, huge offset)

relative reminder
-> resolve_datetime
-> sometimes stops before creating the reminder
```

The explicit-date failures were not Python failures. The model-facing contract required `base`, `offset`, and `unit`, but made `datetime` only conditionally required in prose. Qwen could therefore emit a structurally valid `base=now` call while omitting the explicit date and trying to convert that date into a large offset.

The reminder traces also proved two things at once:

- Qwen3.5-2B can execute dependent multi-round tool workflows;
- a simple relative reminder should not require an artificial read-then-write chain when one action can resolve its own schedule deterministically.

The generic `Agent` loop is therefore retained. The correction is in the capability contracts.

## 2. Design principles

The design follows the same public principles that make Go APIs easy to reason about:

- small public surface;
- one obvious operation for one responsibility;
- one representation for one concept;
- required state should be structurally required, not hidden in prose;
- no artificial workflow when one operation owns the behavior;
- deterministic validation in code;
- no router, planner, graph, registry, or semantic keyword rules;
- observable failures instead of silent normalization.

A small explicit API is preferred over more instructions explaining an ambiguous API.

## 3. Model-facing surface

The current scope requires three tools:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

The model chooses them directly from their schemas.

## 4. Shared temporal representation

Both temporal tools use the same anchor representation:

```json
{
  "reference": "now | ISO-8601 date/datetime",
  "offset": 0,
  "unit": "minutes | hours | days | weeks"
}
```

Rules:

```text
reference="now"
    the request contains no explicit calendar date/datetime

reference=<ISO-8601 value>
    the request contains an explicit calendar date/datetime

offset=0
    resolve the reference itself

offset!=0
    shift the reference by the signed duration
```

There is no separate `base` classifier and no conditionally required `datetime` field.

This matters because an explicit date can no longer be represented as:

```text
base=now
+ invented offset
+ omitted datetime
```

The explicit date itself must occupy the required `reference` slot.

## 5. Tool contracts

### 5.1 `search_portfolio`

Responsibility:

> Retrieve factual evidence specifically about the portfolio subject.

Its schema explicitly excludes general conversation, jokes, creative requests, definitions, and generic knowledge. This boundary belongs in the tool schema because it defines the tool's applicability.

### 5.2 `resolve_datetime`

Responsibility:

> Resolve a date/time value without side effects.

Examples:

```text
today
-> reference="now", offset=0

tomorrow
-> reference="now", offset=1, unit="days"

yesterday
-> reference="now", offset=-1, unit="days"

one week from now
-> reference="now", offset=1, unit="weeks"
   or any semantically equivalent duration

weekday of 2026-12-25
-> reference="2026-12-25", offset=0

five days after 2026-12-25
-> reference="2026-12-25", offset=5, unit="days"
```

The model may normalize equivalent durations differently. The evaluator compares duration semantics rather than serialization.

### 5.3 `set_reminder_mock`

Responsibility:

> Create a simulated reminder and resolve its schedule in the same operation.

Relative reminder:

```text
remind me in 30 minutes
-> set_reminder_mock(
     reference="now",
     offset=30,
     unit="minutes",
     message=...
   )
```

Explicit reminder:

```text
remind me at 2026-09-10T15:00:00-03:00
-> set_reminder_mock(
     reference="2026-09-10T15:00:00-03:00",
     offset=0,
     unit="minutes",
     message=...
   )
```

A separate `resolve_datetime` call is unnecessary for these requests.

The result remains explicit about its mock behavior:

```json
{
  "status": "simulated_only",
  "persisted": false,
  "will_notify": false
}
```

## 6. Multi-round behavior

Multi-round tool execution remains supported by the generic `Agent` loop.

It should be used when a later operation genuinely depends on data produced by an earlier operation. It is not used merely to decompose a capability that can own its deterministic calculation itself.

Therefore:

```text
multi-round support: retained
relative reminder requiring two calls: removed
```

No server-side planner is introduced.

## 7. Runtime implementation

Temporal resolution is shared internally through a deterministic helper:

```text
reference
  -> "now" => current zoned datetime
  -> otherwise => parse ISO-8601 value
  -> apply signed offset
```

Public behavior remains explicit:

```text
resolve_datetime
    -> resolve reference
    -> return date/time details

set_reminder_mock
    -> resolve reference
    -> return simulated reminder result
```

Internal helper reuse does not change the model-facing separation of responsibilities.

## 8. Global prompt responsibility

Tool descriptions remain in the tool schemas.

The system prompt contains only shared operating policy:

```text
Use an external capability only when the request requires information or an action it provides.
Use exact values returned by external capabilities.
Do not claim side effects beyond what a capability result confirms.
```

It does not enumerate tools or duplicate their contracts.

## 9. Evaluation contract

The live evaluator reports separately:

```text
tool selection
parameter extraction
tool execution
answer presence
```

It consumes the diagnostic trace, including exact tool arguments and results.

Semantic durations are normalized:

```text
2 hours == 120 minutes
1 week == 7 days
```

A successful Python call with the wrong schedule is still an evaluation failure.

## 10. Non-goals

This design does not add:

- router;
- planner;
- graph;
- dynamic tool retrieval;
- tool registry;
- server-side semantic keyword rules;
- another LLM call;
- model upgrade;
- sampling changes;
- PocketTrace as a correctness dependency.

## 11. Validation

Run the focused regression gate first:

```bash
cd server
make check
make down
make up
make eval-smoke
```

If the smoke is clean, run the full checkpoint:

```bash
make eval-strict
```

The live trace is the source of truth for tool calls, arguments, execution results, model rounds, provider metadata, and latency.
