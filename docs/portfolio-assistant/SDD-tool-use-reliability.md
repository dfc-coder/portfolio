# SDD — Tool-use reliability

Status: Proposed

Branch: `feat/agent-live-eval`

## 1. Problem

The agent currently has three different reliability problems that were being measured as if they were one:

1. **Tool decision** — deciding whether any tool is needed.
2. **Tool selection** — choosing the correct tool when a tool is needed.
3. **Argument generation** — producing the correct arguments for the selected tool.

The current live evaluator observes tool names and execution failures, but it discards the tool arguments already preserved in the returned conversation context. This makes a successful Python execution look like a successful agent decision even when the model supplied the wrong arguments.

Example: a relative reminder can select `set_relative_reminder_mock` correctly and still be wrong if `30 minutes` becomes `30 days`.

The correction must therefore improve two things independently:

- the **tool contracts** presented to Qwen;
- the **evaluation signal** used to diagnose tool use.

## 2. Design principles

The design follows the same public principles that make Go code easy to maintain:

- Prefer explicit behavior over clever abstraction.
- Keep responsibilities small and orthogonal.
- Use one representation for one concept.
- Do not introduce a framework when a small function is enough.
- A little duplication is acceptable when it keeps the code obvious.
- Errors must be observable instead of silently normalized away.
- Names should explain intent without requiring comments to decode them.

Applied here:

- no router;
- no planner;
- no graph;
- no tool registry;
- no generic schema factory;
- no semantic `if "tomorrow" in message` logic;
- no change to the generic model/tool loop in `Agent` unless strictly necessary.

## 3. Goals

### 3.1 Functional goals

The agent must reliably distinguish these behaviors:

```text
no tool
current time
relative time from now
weekday of a supplied date
shift from a supplied date
action: reminder
```

The model is responsible for choosing a capability and filling its arguments. Python is responsible for deterministic validation and execution.

### 3.2 Evaluation goals

The local live eval must report separately:

```text
tool decision
tool selection
argument correctness
tool execution
answer presence
```

A tool call with correct name but wrong arguments must not count as a successful case.

## 4. Non-goals

This change does not add:

- a planner;
- a router;
- dynamic tool retrieval;
- another LLM call for tool selection;
- PocketTrace as a prerequisite for correctness;
- server-side conversation state;
- new sampling experiments;
- a new test framework.

PocketTrace remains useful for runtime observability later, but the live evaluator must be sufficient to diagnose this issue by itself.

## 5. Existing architecture

The architecture remains:

```text
visitor
  -> API
  -> Agent
      -> Qwen + tool schemas
      -> tool_calls?
          -> execute requested tools
          -> append tool calls and results
          -> repeat
      -> final answer
```

`Agent` already preserves the complete OpenAI-compatible assistant `tool_calls`, including `name` and raw `arguments`, in the conversation context returned at the end of the request.

Therefore the evaluator should consume that existing data instead of changing the public agent protocol just to expose more diagnostics.

## 6. Tool contracts

### 6.1 Naming rule

Tool names must describe the operation and the source of the base value.

Avoid internal vocabulary such as `relative` and `explicit` when a simpler name exists.

Proposed temporal tool names:

```text
get_current_datetime
get_datetime_from_now
get_weekday
shift_datetime
```

The Python schema constants may mirror these names:

```text
GET_CURRENT_DATETIME_SCHEMA
GET_DATETIME_FROM_NOW_SCHEMA
GET_WEEKDAY_SCHEMA
SHIFT_DATETIME_SCHEMA
```

The constant name is only an internal Python identifier. Qwen sees the function name, description, and parameters.

### 6.2 `get_current_datetime`

Purpose:

> Return the actual current date and time in a timezone.

Contract:

```text
base: actual current moment
offset: none
input: optional timezone
```

Schema description:

```text
Return the actual current date and time in a timezone. The request is anchored to now and contains no date or time offset.
```

Examples of intended use:

```text
What date is it today?
What time is it now?
What time is it in Buenos Aires?
```

### 6.3 `get_datetime_from_now`

Purpose:

> Return a date or time obtained by shifting the actual current moment.

Contract:

```text
base: actual current moment
offset: required
input: days, hours, minutes, optional timezone
```

Schema description:

```text
Return the date and time obtained by shifting the actual current moment by a signed duration. The base is always the current moment and is not supplied by the caller. At least one offset must be non-zero.
```

Examples of intended use:

```text
tomorrow            -> days=1
yesterday           -> days=-1
in one week         -> days=7
in two hours        -> hours=2
30 minutes ago      -> minutes=-30
```

The description does not need to name competing tools. The distinction is in the contract itself: the base is always `now`.

### 6.4 `get_weekday`

Purpose:

> Return the weekday for a supplied calendar date.

Contract:

```text
base: supplied YYYY-MM-DD date
offset: none
input: date
```

Schema description:

```text
Return the weekday for a supplied ISO-8601 calendar date in YYYY-MM-DD form. No date arithmetic is performed.
```

Examples:

```text
2026-12-25 -> Friday
2026-01-01 -> Thursday
```

### 6.5 `shift_datetime`

Purpose:

> Shift a supplied date or datetime by a duration.

Contract:

```text
base: supplied date/datetime
offset: required
input: datetime, days, hours, minutes
```

Schema description:

```text
Return the date and time obtained by shifting a supplied ISO-8601 date or datetime by a signed duration. At least one offset must be non-zero.
```

Example:

```text
2026-12-25 + 5 days
```

### 6.6 Reminder tools

Do not rename reminder tools as part of this correction.

Current selection behavior for relative reminders is already materially better than date-tool selection. What is missing is validation of the generated arguments.

Keep:

```text
set_reminder_mock
set_relative_reminder_mock
```

until the evaluator can show whether their names or arguments are actually the source of a failure.

## 7. Runtime implementation

Public tool functions stay small and direct.

Expected shape:

```text
get_current_datetime
    -> now(zone)
    -> datetime result

get_datetime_from_now
    -> now(zone)
    -> timedelta(offset)
    -> datetime result

get_weekday
    -> parse YYYY-MM-DD
    -> datetime result

shift_datetime
    -> parse supplied datetime
    -> timedelta(offset)
    -> datetime result
```

Shared helpers are justified only when they encode a real invariant, for example:

```text
_zone
_parse_datetime
_datetime_result
_require_offset
validation helpers
```

Do not add a generic `Tool`, handler registry, schema builder, or dispatch abstraction only to reduce line count.

The existing explicit dispatch style is acceptable for this number of tools:

```python
if name == "search_portfolio":
    ...

if name == "get_current_datetime":
    ...
```

It is repetitive but obvious.

## 8. Evaluator design

### 8.1 Source of truth

Do not modify `Agent` to expose raw tool arguments in new SSE events.

The final `context` event already contains assistant `tool_calls` and matching tool-result messages. The evaluator should read that context and reconstruct observed calls.

### 8.2 Observed call

Use one small explicit value object:

```python
@dataclass(frozen=True)
class ObservedCall:
    name: str
    arguments: dict[str, Any]
    ok: bool
```

No generic trace framework is needed.

### 8.3 Expected call

Replace the duplicated `expected_tools` / `forbidden_tools` model with one source of truth:

```json
{
  "expected_calls": [
    {
      "name": "get_datetime_from_now",
      "arguments": {"days": 1}
    }
  ]
}
```

For cases where argument wording is intentionally flexible, omit `arguments`:

```json
{
  "expected_calls": [
    {"name": "search_portfolio"}
  ]
}
```

For a no-tool case:

```json
{
  "expected_calls": []
}
```

Extra calls already make the expected and actual call lists differ, so a separate `forbidden_tools` field is unnecessary.

Keep `tool_order` only where ordering is meaningful; `any` remains useful for independent parallel calls.

### 8.4 Pass criteria

A local live-eval case passes only when:

```text
no agent error
AND final answer is non-empty
AND expected tool decision is correct
AND expected tool names are correct
AND expected arguments are correct when specified
AND every tool execution succeeds
```

This means:

```text
correct tool + wrong arguments = FAIL
```

### 8.5 Metrics

Report:

```text
tool decision accuracy
selection accuracy
argument accuracy
tool execution success
overall pass rate
latency p50/p95
```

`tool execution success` means only that the Python tool returned `ok=true`. It must never be presented as evidence that the model chose the correct tool or arguments.

## 9. Test responsibility split

Keep three levels, each with one job.

### Unit tests

`test_tools.py`

Validate deterministic Python behavior:

```text
parsing
timezone behavior
date arithmetic
weekday computation
reminder target calculation
validation errors
```

### Live eval

`run_agent_eval.py`

Validate model behavior:

```text
use tool or not
which tool
which arguments
execution success
```

### QwenCloud eval

Validate final natural-language behavior later:

```text
task correctness
grounding/truthfulness
response quality
```

Do not make the local evaluator duplicate semantic LLM judging.

## 10. Required smoke behavior

The existing smoke set should express these contracts:

```text
Hola
  -> []

¿Qué fecha será mañana?
  -> get_datetime_from_now {days: 1}

¿Qué día de la semana fue ayer?
  -> get_datetime_from_now {days: -1}

¿Qué día cae 2026-12-25?
  -> get_weekday {date: "2026-12-25"}

¿Qué fecha será dentro de una semana?
  -> get_datetime_from_now {days: 7}

¿Qué día fue 2026-01-01?
  -> get_weekday {date: "2026-01-01"}

Recordame en 30 minutos ...
  -> set_relative_reminder_mock {minutes: 30, ...}

Recordame en 2 horas ...
  -> set_relative_reminder_mock {hours: 2, ...}

Recordame en 7 días ...
  -> set_relative_reminder_mock {days: 7, ...}
```

The exact reminder message text may be checked separately from the temporal offset if necessary, but the offset value must be deterministic.

## 11. Implementation order

Implement in this order:

1. Make the evaluator preserve and print observed tool arguments from the existing returned context.
2. Change eval cases to the single `expected_calls` representation.
3. Run the same smoke test without changing tool schemas. This establishes the real baseline for selection and arguments.
4. Rename and clarify only the temporal tool contracts defined in this document.
5. Update the existing unit tests and eval cases for the renamed contracts.
6. Run `make check`.
7. Run the same `make eval-smoke` once.
8. Only if failures remain, use the observed call and arguments to make a localized schema correction.

Do not change sampling, prompt architecture, or agent control flow during this sequence.

## 12. Acceptance criteria

The correction is accepted when the smoke run shows:

```text
general: 2/2
reminder: 3/3
date_time: 5/5
tool execution: 10/10
argument checks: all applicable cases correct
```

and no new router, planner, registry, or semantic branching exists in `Agent`.

## 13. References

- JTPRO: https://arxiv.org/html/2604.19821
- Qwen function calling documentation and model tool schema behavior
- Agent tooling anti-pattern discussion supplied for this work
