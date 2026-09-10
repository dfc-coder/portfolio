# Turn execution trace

Diagnostics record observable execution only; hidden reasoning is not exposed.

A trace contains:

```text
input
model configuration
dispatch routes
worker rounds
  request messages
  finish reason
  usage/timings
  generated content
  tool calls
    raw + parsed arguments
    result
    duration
    reused flag when applicable
final answer
returned context
error
```

The `tools` field records the tool schemas visible to that worker. Returned tool names are checked against the worker's allowed set before execution.

The current model name is configuration-driven; local evaluation uses `Qwen3.5-4B`.

An executed tool call records:

```json
{
  "id": "call-id",
  "name": "tool_name",
  "arguments_raw": "{...}",
  "arguments": {},
  "duration_ms": 0.0,
  "ok": true,
  "result_raw": "{...}",
  "result": {}
}
```

A repeated successful call may also contain `"reused": true`; the prior result is reused with the new `tool_call_id`.

`ok=true` proves only deterministic tool execution succeeded. It does not prove tool selection or semantic argument extraction was correct.

Diagnostics require `AGENT_DIAGNOSTICS_TOKEN` and the matching `X-Agent-Diagnostics-Token` request header.
