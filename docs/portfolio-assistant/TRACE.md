# Turn execution trace

The diagnostic trace records the complete observable execution of one agent turn without changing the model/tool decision flow.

Diagnostics are disabled unless `AGENT_DIAGNOSTICS_TOKEN` is configured and the request supplies the same value in `X-Agent-Diagnostics-Token`. Normal portfolio requests do not receive traces.

## Trace scope

One trace represents one visitor turn and contains:

```text
turn
  input
  model configuration
  tool schemas presented to the model
  round 1
    exact request messages
    provider response metadata
    finish reason
    usage
    timings
    generated content
    tool calls
      raw arguments
      parsed arguments
      execution result
      duration
  round N...
  final answer
  returned context
  total duration
  error
```

## Top-level fields

```json
{
  "trace_id": "uuid",
  "started_at": "UTC ISO-8601",
  "finished_at": "UTC ISO-8601",
  "duration_ms": 0.0,
  "status": "ok|error",
  "input": {
    "message": "...",
    "context": []
  },
  "model": {
    "name": "Qwen3.5-2B",
    "generation": {}
  },
  "tools": [],
  "rounds": [],
  "output": "...",
  "returned_context": [],
  "error": null
}
```

## Round metadata

Each model round records the exact messages sent to the provider and the observable response metadata:

```json
{
  "round": 1,
  "request_messages": [],
  "response": {
    "id": "chatcmpl-...",
    "object": "chat.completion.chunk",
    "model": "Qwen3.5-2B",
    "created": 0,
    "system_fingerprint": "...",
    "finish_reason": "tool_calls|stop|length",
    "usage": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0
    },
    "timings": {},
    "provider": {},
    "content": "",
    "chunk_count": 0,
    "first_delta_ms": 0.0,
    "first_text_ms": 0.0,
    "duration_ms": 0.0
  },
  "assistant_message": {},
  "tool_calls": []
}
```

Provider-specific top-level fields that are not part of the stable trace schema are retained under `response.provider` instead of being discarded. This includes llama.cpp diagnostic fields when available.

When diagnostics are enabled the request asks llama.cpp for:

```text
stream_options.include_usage = true
verbose = true
timings_per_token = true
return_progress = true
```

This makes token usage, prompt/generation timings, cache-related timing data and provider debug metadata observable when the running llama.cpp build exposes them.

## Tool call metadata

Every executed tool call is represented once:

```json
{
  "id": "call-id",
  "name": "tool_name",
  "arguments_raw": "{...}",
  "arguments": {},
  "started_at": "UTC ISO-8601",
  "finished_at": "UTC ISO-8601",
  "duration_ms": 0.0,
  "ok": true,
  "result_raw": "{...}",
  "result": {}
}
```

This is the data needed to distinguish:

```text
tool decision accuracy
  Did the model call a tool when required?

tool selection accuracy
  Did it choose the correct tool?

parameter extraction accuracy
  Did it generate the correct argument names and values?

tool execution success
  Did the deterministic implementation execute successfully?

end-to-end success
  Did the full turn produce the correct final behavior?
```

A tool execution that returns `ok=true` does not imply that the model supplied correct arguments. Those are separate measurements.

## Security

The trace may contain system instructions, conversation context, tool arguments and tool results. It is therefore not exposed by default and must not be enabled in a public deployment without an explicit diagnostics access policy.

Reasoning text is not recorded. If a provider emits a reasoning field, the trace may record only that such content was present, not the hidden reasoning itself.

## Local eval

Set the same local token in `server/.env` used by the API:

```env
AGENT_DIAGNOSTICS_TOKEN=local-eval-only
```

`run_agent_eval.py` reads the token from the environment or `server/.env`, sends it in `X-Agent-Diagnostics-Token`, stores the full trace under each case in the results JSON, and prints a concise round/tool summary to the terminal.
