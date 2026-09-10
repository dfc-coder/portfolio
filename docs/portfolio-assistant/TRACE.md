# Turn execution trace

The diagnostic trace records the observable execution of one agent turn without changing the model/tool decision flow.

Diagnostics are disabled unless `AGENT_DIAGNOSTICS_TOKEN` is configured and the request supplies the same value in `X-Agent-Diagnostics-Token`.

## Trace scope

One trace contains:

```text
turn
  input
  model configuration
  registered tool schemas presented to the model
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
      reused flag when applicable
  round N...
  final answer
  returned context
  total duration
  error
```

The `tools` field is the registered model-facing tool surface for the turn. Returned tool names are checked against that registry before execution.

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
    "name": "Qwen3.5-2B-Q6_K",
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

Each model round records the exact messages sent to the provider and observable response metadata:

```json
{
  "round": 1,
  "request_messages": [],
  "response": {
    "id": "chatcmpl-...",
    "object": "chat.completion.chunk",
    "model": "Qwen3.5-2B-Q6_K",
    "created": 0,
    "system_fingerprint": "...",
    "finish_reason": "tool_calls|stop|length",
    "usage": {},
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

Provider-specific top-level fields not part of the stable trace schema are retained under `response.provider`.

When diagnostics are enabled the request asks llama.cpp for:

```text
stream_options.include_usage = true
verbose = true
timings_per_token = true
return_progress = true
```

## Tool call metadata

An executed tool call is represented as:

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

When an identical successful call is returned again, the trace also contains:

```json
{
  "reused": true,
  "duration_ms": 0.0
}
```

The prior result is reused with the new `tool_call_id`; the handler is not executed again.

The trace supports separate measurements for:

```text
tool decision accuracy
tool selection accuracy
parameter extraction accuracy
tool execution success
end-to-end success
```

A tool result with `ok=true` means only that deterministic server execution succeeded. It does not prove the model chose the correct tool or arguments.

## Conversation context

The API associates turns with a `conversation_id`. The server stores complete OpenAI-compatible context, including assistant tool calls and matching tool results.

The client may round-trip context as a recovery seed after a server restart.

Conversation history is trimmed only at user-message boundaries so stored context does not begin in the middle of an assistant/tool exchange.

## Security

The trace may contain system instructions, conversation context, tool arguments and tool results. It is therefore not exposed by default.

Reasoning text is not recorded. If a provider emits a reasoning field, the trace may record only that such content was present.

## Local eval

Set the same local token in `server/.env` used by the API:

```env
AGENT_DIAGNOSTICS_TOKEN=local-eval-only
```

`run_agent_eval.py` reads the token from the environment or `server/.env`, sends it in `X-Agent-Diagnostics-Token`, stores the trace under each case, and prints a concise round/tool summary.
