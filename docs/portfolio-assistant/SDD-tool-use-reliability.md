# SDD — Go-like reliable agent runtime

Status: Implemented, pending live Qwen3.5-2B Q6 validation

Branch: `feat/agent-live-eval`

## 1. Objective

The portfolio assistant uses one explicit model/tool loop with a small number of runtime invariants.

The architecture must remain:

- readable from top to bottom;
- explicit about control flow;
- small in number of abstractions;
- independent of semantic routers and agent frameworks;
- safe to extend with additional tools without modifying the Agent.

Behavioral evals validate the chosen local SLM. They are not used to create routing architecture around model failures.

## 2. Runtime

```text
visitor
  -> conversation session
  -> Agent
      -> model + registered tool schemas
      -> final answer?
          -> stream final text
          -> return
      -> tool calls?
          -> keep intermediate text internal
          -> validate registered names
          -> validate arguments
          -> execute in call order
          -> append assistant tool calls
          -> append matching tool results
          -> next model round
  -> persist complete returned context
```

There is no semantic router, capability gate, ToolSearch, reranker, planner, graph, or agent framework.

The main model is the semantic authority deciding whether a registered tool is needed. Deterministic server policy still owns validation and execution.

## 3. Model

The local runtime is:

```text
llama.cpp
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-Q6_K.gguf
```

The API uses llama.cpp's OpenAI-compatible chat completions interface with Jinja tool calling enabled and Qwen thinking disabled.

Generation defaults for the local acceptance gate:

```text
temperature = 0.0
top_p = 1.0
top_k = 1
```

These are configuration values, not Agent branching rules.

## 4. Tool registry

The production surface is currently:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` owns the simple registry:

```text
Tool
  schema
  run
```

Adding a tool requires defining its schema, implementing its handler, and adding one registry entry. The Agent receives schemas from the registry and contains no per-tool branching.

## 5. Tool execution invariants

Before execution:

```text
returned tool name must exist in the registry
arguments must be valid for that tool
```

Calls returned in one model round are executed in model call order. Parallel model calls are supported as a protocol shape, but execution stays sequential and deterministic.

A successful call is keyed by tool name plus canonical JSON arguments. If the same successful call appears again in the same turn, the prior result is reused with the new `tool_call_id`; the handler is not executed twice.

This applies per call. For:

```text
repeated A + new B
```

A is reused and only B executes.

If an entire model round contains only repeated successful calls, tools are removed for the next model round to force a final answer.

## 6. Multi-round protocol

For every model tool call:

```text
assistant
  tool_calls:
    id=A
    function=...

tool
  tool_call_id=A
  content=...
```

The exact call id is preserved.

The loop supports both chained and same-round calls:

```text
round 1 -> tool A
round 2 -> tool B
round 3 -> final answer
```

```text
round 1 -> tool A + tool B
round 2 -> final answer
```

Only the text from a final round with no tool calls is exposed as visitor-facing `token` events. Text emitted by the model during a tool-call round remains internal so the UI does not show transient phrases such as "I will check" before the actual answer.

A hard tool-round limit prevents infinite loops while still allowing a final answer round after the last permitted tool round.

## 7. Conversation state

The API accepts an optional `conversation_id` UUID and emits the resolved id as an SSE `conversation` event.

The in-memory store preserves complete OpenAI-compatible history:

```text
user
assistant tool_calls
tool result
assistant
user
...
```

The server session is the source of truth while alive. Client context may seed a session after restart.

History is bounded and trimmed at a user-message boundary so it does not begin in the middle of a tool exchange.

Durable storage can replace the store later without modifying the Agent protocol.

## 8. Retrieval

Portfolio retrieval remains a separate read-only capability backed by `Qwen3-Embedding-0.6B`.

The embedding service is infrastructure for `search_portfolio`; it does not route or select tools.

## 9. Tracing

Diagnostic traces record registered tool schemas, model rounds, finish reasons, tool calls, raw and parsed arguments, results, timings, reused calls, and returned context. Hidden reasoning is not exposed.

## 10. Testing

Deterministic runtime tests cover:

```text
registered schemas are sent to the model
unknown tool is rejected
streamed tool-call fragments are reconstructed
tool_call_id is preserved
multi-round chains preserve prior results
multiple calls preserve call order
identical successful calls execute once
repeated A + new B does not execute A twice
intermediate tool-round text is not exposed
conversation state retains tool messages
history trimming starts at a user boundary
```

Live evals then measure whether the local Qwen3.5-2B Q6 chooses the correct tool, extracts valid arguments, and produces the expected final response.

A behavioral model failure is diagnosed as a model/schema/prompt problem first. It does not justify adding a semantic router unless a future product requirement establishes a separate deterministic policy boundary.
