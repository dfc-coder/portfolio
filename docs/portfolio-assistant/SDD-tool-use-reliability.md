# SDD — Tool-use reliability

Status: Implemented, pending live regression validation

Branch: `feat/agent-live-eval`

## 1. Problem

The live traces showed that the reliability issue was not a Python execution bug and not a multi-round runtime bug.

The failure was caused by an unnecessarily overlapping model-facing tool surface.

With seven tools, Qwen had to distinguish between multiple capabilities that could all appear relevant to the same temporal request:

```text
get_current_datetime
get_datetime_from_now
shift_datetime
get_weekday_for_explicit_date
set_reminder_mock
set_relative_reminder_mock
search_portfolio
```

The traces showed concrete collisions:

```text
tomorrow
-> get_current_datetime

yesterday weekday
-> get_weekday_for_explicit_date with an invented date

one week
-> get_current_datetime

remind me in 30 minutes
-> get_datetime_from_now, then stop

remind me in 2 hours
-> get_datetime_from_now
-> set_reminder_mock
```

The last case is important: Qwen successfully completed a dependent multi-round workflow. The generic `Agent` loop is therefore capable of multi-round tool execution.

The tool surface, not the loop, was the primary design problem.

## 2. Design principles

The correction follows the same public design philosophy that makes Go APIs easy to reason about:

- small public surface;
- one obvious operation for one responsibility;
- explicit data contracts;
- no router when the API itself can be simpler;
- no framework or registry to hide three straightforward operations;
- deterministic validation in code;
- model reasoning only where natural-language interpretation is unavoidable;
- observable failures instead of silent normalization.

A little implementation code is preferable to multiple overlapping public abstractions.

## 3. Decision

Reduce the model-facing tool surface from seven tools to three:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

This is not a routing optimization. It is an API correction.

The model still chooses tools directly from their schemas. There is no semantic router, keyword matching, planner, graph, or additional LLM call.

## 4. Tool contracts

### 4.1 `search_portfolio`

Responsibility:

> Retrieve factual evidence from the portfolio/CV.

It remains unchanged.

### 4.2 `resolve_datetime`

Responsibility:

> Deterministically resolve current, relative, or supplied date/time values.

It is read-only.

Schema shape:

```json
{
  "base": "now | provided",
  "datetime": "optional ISO-8601 input",
  "offset": 0,
  "unit": "minutes | hours | days | weeks",
  "timezone": "optional IANA timezone"
}
```

Rules:

```text
base=now
    datetime must be omitted

base=provided
    datetime must be copied from the request

offset=0
    no arithmetic

offset!=0
    shift the selected base
```

Examples of semantics:

```text
today
-> base=now, offset=0

tomorrow
-> base=now, +1 day

yesterday
-> base=now, -1 day

one week from now
-> base=now, +1 week
   or any semantically equivalent duration

weekday of a supplied date
-> base=provided, datetime=<supplied date>, offset=0

five days after a supplied date
-> base=provided, datetime=<supplied date>, +5 days
```

The evaluator compares duration semantics, not a preferred serialization. `2 hours` and `120 minutes` are equivalent.

### 4.3 `set_reminder_mock`

Responsibility:

> Create a simulated reminder for an absolute datetime.

It does not resolve relative time.

For an explicit absolute reminder:

```text
user
-> set_reminder_mock
```

For a relative reminder:

```text
user
-> resolve_datetime
-> set_reminder_mock
```

This is a real dependency and therefore a valid multi-round workflow.

The reminder result explicitly states:

```json
{
  "status": "simulated_only",
  "persisted": false,
  "will_notify": false
}
```

No real notification is created.

## 5. Why the previous design failed

### 5.1 Tool-selection overlap

The traces proved that descriptions alone were not enough to make Qwen consistently distinguish:

```text
current moment
relative moment
weekday
date arithmetic
relative reminder
```

because several tools represented overlapping portions of the same temporal domain.

Adding more prose to each schema would increase instruction density without removing the competing affordances.

The correction removes the overlap.

### 5.2 Parameter representation

The previous `days/hours/minutes` contract encoded the unit in the property name.

The intermediate `offset + unit` contract was structurally better, but the evaluator incorrectly treated equivalent representations as different:

```text
2 hours
120 minutes
```

For correctness, these represent the same duration.

The runtime keeps `offset + unit`; the evaluator normalizes them to seconds when comparing expected behavior.

### 5.3 Multi-round

The traces do not support the claim that Qwen3.5-2B cannot execute multi-round workflows.

A reminder case successfully executed:

```text
resolve relative target
-> create absolute reminder
-> final response
```

Therefore multi-round remains part of the architecture when a real data dependency exists.

## 6. Runtime architecture

Unchanged:

```text
visitor
  -> API
  -> Agent
      -> Qwen + tool schemas
      -> tool call?
          -> Python validates and executes
          -> assistant tool call + tool result appended
          -> next model round
      -> final answer
```

`Agent` remains generic.

It does not know that a reminder needs a date calculation.

That behavior comes from the model-facing tool contracts.

## 7. Final-answer grounding

The traces also exposed a separate issue: Qwen could receive a correct structured result and then alter or contradict it in natural language.

Examples included:

```text
tool result: will_notify=false
final answer: notification will be sent automatically
```

The global prompt therefore contains only shared result-grounding policy:

```text
Use exact values returned by external capabilities.
Do not recalculate, replace, or contradict them.
Do not claim side effects beyond what a capability result confirms.
```

This is not a duplicate of any tool schema. It is a general response invariant.

## 8. Evaluation contract

The local evaluator now separates:

```text
tool selection
parameter extraction
tool execution
answer presence
```

It also validates:

### Semantic duration equivalence

```text
2 hours == 120 minutes
1 week == 7 days
```

### Multi-round value propagation

For relative reminders:

```text
resolve_datetime.result.datetime
==
set_reminder_mock.arguments.datetime
```

A reminder that uses an invented target datetime fails even if both tools execute successfully.

## 9. Non-goals

This correction does not add:

- router;
- planner;
- graph;
- dynamic tool retrieval;
- tool registry;
- server-side semantic keyword rules;
- model upgrade;
- sampling changes;
- PocketTrace as a correctness dependency.

## 10. Model-facing surface

Final surface for the current agent scope:

```text
1. search_portfolio
2. resolve_datetime
3. set_reminder_mock
```

Three tools are sufficient for the current requirements.

Additional tools should be added only when a genuinely new external capability exists, not to represent another linguistic variation of an existing operation.

## 11. Validation

Run:

```bash
cd server
make check
make down
make up
make eval-smoke
```

The smoke is the immediate regression gate.

After the smoke is clean, run the full 50-case checkpoint:

```bash
make eval-strict
```

The local live run remains the source of truth for tool calls, arguments, execution results, round sequencing, provider metadata, and latency.
