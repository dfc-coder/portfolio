# SDD — Tool-use reliability

Status: Implemented, pending live regression validation

Branch: `feat/agent-live-eval`

## 1. Problem

The traced live evaluation showed three independent failure classes:

1. **Tool selection** — choosing the wrong capability.
2. **Parameter extraction** — choosing the right capability but encoding the requested value in the wrong slot.
3. **Tool execution** — deterministic validation or execution failure after a call is produced.

The previous evaluator only checked tool names and execution status, so calls such as `2 hours -> days=2` could be reported as successful.

## 2. Trace-backed diagnosis

The failures are not caused by the deterministic datetime implementation and are not primarily a multi-round limitation.

Observed examples:

```text
"tomorrow"
  -> get_current_datetime {}
  -> wrong tool selection

"yesterday"
  -> get_weekday_for_explicit_date {date: 2026-12-24}
  -> wrong tool + invented date

"one week"
  -> get_relative_datetime {days: 1}
  -> correct capability, wrong slot representation

"in 2 hours"
  -> set_relative_reminder_mock {days: 2}
  -> correct capability, wrong unit

"in 30 minutes"
  -> set_relative_reminder_mock {days: 0}
  -> validation failure
  -> next model round retries with {minutes: 30}
  -> succeeds
```

The `30 minutes` recovery proves that the existing model/tool loop can execute multi-round correction. The failure is therefore upstream in the model-facing capability contract.

The old temporal contract exposed several optional numeric fields:

```text
days?
hours?
minutes?
```

with no required duration field and no `weeks` unit. The runtime then imposed an additional invariant that the schema did not express: at least one offset had to be non-zero.

That representation created two problems:

- **slot ambiguity:** the model had to choose which numeric field represented the unit;
- **forced conversion:** `one week` had to be converted by the model into `days=7`.

Concrete calendar values inside schema descriptions also leaked anchors into a small model. A relative request for `yesterday` produced `2026-12-24`, immediately adjacent to the old schema example `2026-12-25`.

## 3. Design principles

The correction follows the same principles used for small, maintainable Go APIs:

- one concept has one representation;
- required state is structurally required;
- names describe the operation rather than an internal classification;
- validation stays deterministic;
- prefer explicit code over generic frameworks;
- do not add a router when the tool contract itself can be made clear;
- do not duplicate tool descriptions in the system prompt;
- avoid hidden conversions when the caller can state the original unit directly.

No planner, graph, semantic router, tool registry, schema factory, or message keyword routing is introduced.

## 4. Architecture

The runtime remains:

```text
visitor
  -> API
  -> Agent
      -> Qwen + tool schemas
      -> tool_calls?
          -> execute requested tools
          -> append assistant tool_calls + matching tool results
          -> repeat
      -> final answer
```

The model chooses capabilities and arguments. Python validates and executes them.

## 5. Model-facing tools

The agent exposes seven tools:

```text
search_portfolio
get_current_datetime
get_datetime_from_now
shift_datetime
get_weekday_for_explicit_date
set_reminder_mock
set_relative_reminder_mock
```

### `get_current_datetime`

```text
base: actual current moment
offset: none
```

Used for the current moment only. It performs no date arithmetic.

### `get_datetime_from_now`

```text
base: actual current moment
offset: required
```

Arguments:

```json
{
  "offset": 1,
  "unit": "weeks"
}
```

`unit` is one of:

```text
minutes
hours
days
weeks
```

The request magnitude and unit are preserved:

```text
tomorrow       -> {offset: 1,  unit: days}
yesterday      -> {offset: -1, unit: days}
one week       -> {offset: 1,  unit: weeks}
two hours      -> {offset: 2,  unit: hours}
30 minutes ago -> {offset: -30, unit: minutes}
```

The model does not convert weeks to days or hours to minutes.

### `get_weekday_for_explicit_date`

```text
base: exact YYYY-MM-DD copied from the request
offset: none
```

The schema contains no concrete example date that the model can copy or transform.

### `shift_datetime`

```text
base: explicit date/datetime copied from the request
offset: required
```

Arguments:

```json
{
  "datetime": "<ISO-8601 value from the request>",
  "offset": 5,
  "unit": "days"
}
```

This tool exists only for arithmetic on a supplied base date. It does not overlap with explicit weekday lookup.

### Reminder tools

`set_reminder_mock` accepts an absolute datetime supplied by the request.

`set_relative_reminder_mock` uses the same `offset + unit` representation as `get_datetime_from_now`:

```json
{
  "message": "Enviar el CV",
  "offset": 2,
  "unit": "hours"
}
```

Reminder results explicitly state:

```json
{
  "status": "simulated_only",
  "persisted": false,
  "will_notify": false
}
```

## 6. Runtime validation

JSON Schema defines the shape that Qwen sees:

- required fields;
- argument types;
- unit enum;
- no additional properties.

Python owns deterministic bounds and semantic invariants:

- `offset` must be an integer;
- `offset` must be non-zero for model-facing arithmetic calls;
- unit must be supported;
- datetime strings must parse;
- absolute reminder datetimes must contain a timezone offset.

Large numeric min/max rules are intentionally kept out of model-facing schemas. This avoids generating unnecessarily large llama.cpp grammar productions while preserving the same runtime protection.

## 7. Evaluator

The evaluator consumes the diagnostic trace and represents a call as one object:

```text
ObservedCall
  name
  arguments
  ok
```

Cases declare `expected_calls` instead of parallel expected/forbidden lists.

Example:

```json
{
  "expected_calls": [
    {
      "name": "get_datetime_from_now",
      "arguments": {
        "offset": 1,
        "unit": "weeks"
      }
    }
  ]
}
```

The runner reports separately:

```text
tool selection accuracy
parameter extraction accuracy
tool execution success
overall pass rate
```

A correct tool with incorrect arguments is a failed case.

## 8. Acceptance criteria

The focused smoke must show all ten cases passing with:

```text
tool selection: 10/10
parameter extraction: all parameterized cases correct
tool execution success: 10/10
overall: 10/10
```

Only after that focused regression passes should the complete 50-case checkpoint be run.

## 9. Out of scope

This correction does not change:

- the system prompt into a tool-routing prompt;
- sampling settings;
- model size;
- llama.cpp serving architecture;
- conversation persistence;
- PocketTrace integration;
- tool count through a router or retriever.

Those remain independent concerns and must not be mixed into this correction without evidence.
