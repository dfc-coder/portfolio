# Portfolio Assistant Trace

Diagnostic traces are a local evaluation and debugging surface. They must expose execution metadata without exposing hidden model reasoning.

## Top-level turn

A diagnostic turn records:

```text
trace_id
started_at
finished_at
duration_ms
status
input
dispatch
workers
rounds
output
returned_context
error
```

`dispatch.routes` contains one or more closed domains:

```text
general
portfolio
datetime
reminder
```

## Worker paths

General and portfolio use the normal worker trace. Portfolio may contain native model tool calls.

Datetime and reminder use the structured temporal fast path. Their trace records the structured parser model round followed by the deterministic Python operation in the same observable call collection.

The direct temporal operation record includes:

```json
{
  "name": "resolve_datetime",
  "arguments": {
    "reference": "now",
    "offset": 1,
    "unit": "days"
  },
  "ok": true,
  "direct": true
}
```

or `set_reminder_mock` for reminder requests.

`direct=true` means the operation was selected by the dispatcher route and executed by Python after structured semantic parsing. It was not emitted through llama.cpp native tool calling.

This compatibility shape is intentional: the live eval can compare tool/operation selection, argument extraction, and execution success against the M0 native-tool baseline.

## Model round metadata

When available, rounds may include:

```text
finish_reason
usage
timings
system_fingerprint
prompt progress
first token / delta timings
provider-specific non-reasoning metadata
```

Hidden reasoning is never surfaced.

For structured datetime/reminder parsing:

```text
stream=false
native_tools=false
```

For the portfolio native-tool loop:

```text
stream=true
tools=[search_portfolio]
```

## Tool / operation record

Each operation record can contain:

```text
id
name
arguments_raw
arguments
started_at
finished_at
duration_ms
ok
result_raw
result
reused
direct
```

`reused=true` applies to an identical successful call reused by the native portfolio loop.

`direct=true` applies to datetime/reminder fast-path execution.

## Conversation state

`returned_context` is the context persisted for the conversation after the turn.

Native portfolio exchanges may include assistant `tool_calls` and matching tool messages because those messages are part of the model protocol.

Datetime/reminder fast-path execution does not manufacture native tool protocol messages. The stored conversation contains the visitor request and final visitor-facing answer.

## Safety

Diagnostic traces are emitted only when the request supplies the configured diagnostics token. Deployed environments should leave diagnostics disabled unless explicitly required.

The trace must never include secrets or hidden chain-of-thought.
