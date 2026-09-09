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
          -> return
      -> tool calls?
          -> validate registered names
          -> validate arguments
          -> execute in call order
          -> append assistant tool calls
          -> append matching tool results
          -> next model round
  -> persist complete returned context
```

There is no:

```text
semantic router
capability gate
ToolSearch
reranker
planner
graph
agent framework
```

The main model is the only semantic authority deciding whether a registered tool is needed.

## 3. Model

The local runtime is:

```text
llama.cpp
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-Q6_K.gguf
```

The API uses llama.cpp's OpenAI-compatible chat completions interface with Jinja tool calling enabled and Qwen thinking disabled.

Generation defaults are deterministic for the local acceptance gate:

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

`app/tools.py` owns a simple registry.

Conceptually:

```text
Tool
  schema
  run
```

Adding a tool requires defining its schema, implementing its handler, and adding one registry entry.

The Agent receives schemas from the registry and resolves returned tool names against the same registry. The Agent contains no per-tool branching.

## 5. Tool execution invariants

Before execution:

```text
returned tool name must exist in the registry
arguments must be valid for that tool
```

The model does not receive authority to bypass server validation.

Calls returned in one model round are executed in model call order. This is intentionally sequential. Parallel model calls are supported as a protocol shape, but execution stays deterministic and side-effect-safe.

A successful call is keyed by:

```text
tool name + canonical JSON arguments
```

If the model returns the same successful call again in the same turn, the prior result is reused with the new `tool_call_id`; the tool is not executed twice.

This applies per call, so a round containing:

```text
repeated A + new B
```

reuses A and executes only B.

If an entire model round consists of already successful repeated calls, tools are removed for the next round to force a final answer.

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

The loop supports:

```text
round 1 -> tool A
round 2 -> tool B
round 3 -> final answer
```

and:

```text
round 1 -> tool A + tool B
round 2 -> final answer
```

A hard model-round limit prevents infinite loops.

## 7. Conversation state

The API accepts an optional `conversation_id` UUID and emits the resolved id as an SSE `conversation` event.

The in-memory store preserves the complete OpenAI-compatible conversation:

```text
user
assistant tool_calls
tool result
assistant
user
...
```

The server session is the source of truth while alive. Client context may seed a session after restart.

History is bounded and trimmed at a user-message boundary so it does not start in the middle of a tool exchange.

Durable storage can replace the store later without modifying the Agent protocol.

## 8. Retrieval

Portfolio retrieval remains a separate read-only capability backed by the embedding model.

The embedding service is infrastructure for `search_portfolio`; it is not a router for tool selection.

## 9. Tracing

Diagnostic traces record:

```text
registered tool schemas
model rounds
finish reasons
assistant tool calls
raw + parsed arguments
tool results
tool timings
reused calls
returned context
```

Hidden model reasoning is not exposed.

## 10. Testing

Deterministic tests must cover runtime invariants directly:

```text
registered schemas are sent to the model
unknown tool is rejected
streamed tool-call fragments are reconstructed
tool_call_id is preserved
multi-round chains preserve prior results
multiple calls preserve call order
identical successful calls execute once
repeated A + new B does not execute A twice
conversation state retains tool messages
history trimming starts at a user boundary
```

Live evals then measure whether the local Qwen3.5-2B Q6 model chooses the correct tool, extracts valid arguments, and produces the expected final response.

A behavioral model failure is diagnosed as a model/schema/prompt problem first. It does not justify adding a semantic router unless the product requirements later establish a separate deterministic policy boundary.
