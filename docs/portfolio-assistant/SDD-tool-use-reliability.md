# SDD — Reliable agent runtime

Status: Implemented, pending local runtime validation

Branch: `feat/agent-live-eval`

## 1. Objective

The runtime must provide three independent guarantees:

1. only tools eligible for the current turn can execute;
2. tool calls can continue across multiple model rounds with exact tool-call/result linkage;
3. complete conversation context, including tool calls and tool results, survives across user turns.

Behavioral evals are acceptance checks. They are not the architecture.

## 2. Runtime

```text
visitor
  -> conversation session
  -> capability eligibility gate
  -> Agent
      -> model + eligible tool schemas
      -> tool call?
          -> validate eligibility
          -> validate arguments
          -> execute
          -> append assistant tool call
          -> append matching tool result
          -> next model round
      -> final answer
  -> persist complete returned context
```

The production tool surface remains:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

Their model-facing contracts are unchanged by this runtime milestone.

## 3. Capability eligibility

Before the conversational model receives any production tools, a small constrained capability gate selects the minimum capability set needed for the current visitor message.

Possible capabilities:

```text
portfolio
datetime
reminder
```

All false means the main model receives no tool schemas at all.

Examples of eligibility semantics:

```text
greeting / thanks / joke / general knowledge
-> []

portfolio fact
-> [portfolio]

date/time calculation
-> [datetime]

create/change reminder
-> [reminder]

mixed portfolio + date request
-> [portfolio, datetime]
```

The gate considers recent conversation only to resolve follow-ups. If an exact answer is already present in context, no capability is required just to retrieve it again.

The Agent also performs a deterministic server-side check before execution:

```text
requested tool name must belong to the eligible tool set
```

Therefore a production tool that was not made eligible cannot execute even if a provider were to return such a call.

The gate fails closed: an invalid gate response raises an error instead of exposing all tools.

## 4. Multi-round tools

The Agent loop remains generic.

```text
model round 1
  -> tool A
  -> result A

model round 2 receives:
  assistant tool_call A
  tool result A with matching tool_call_id

model round 2
  -> tool B
  -> result B

model round 3
  -> final answer
```

The same loop supports multiple tool calls in one model round. Results are appended in call order and each result keeps the original `tool_call_id`.

Validation errors are returned as tool results, allowing the next model round to recover without special-case orchestration.

A hard round limit prevents infinite tool loops.

## 5. Conversation sessions

The API accepts an optional `conversation_id` UUID and always emits the resolved id as an SSE `conversation` event.

The server stores the complete OpenAI-compatible context returned by the Agent:

```text
user
assistant tool_calls
tool result
assistant
user
...
```

A subsequent request carrying the same `conversation_id` uses server context as the source of truth.

The browser still sends its latest context as a recovery seed. If the server process has restarted and no in-memory session exists, that seed can reconstruct the session without changing the protocol.

History is bounded and trimmed only at a user-message boundary, so stored context never begins halfway through an assistant/tool exchange.

The current store is intentionally in-memory and bounded. Durable storage can replace it later without changing the Agent or API contract.

## 6. Tracing

A diagnostic turn trace now records:

```text
capability gate decision
eligible tool schemas
model rounds
assistant tool calls
raw + parsed arguments
tool results
tool timings
final context
```

The trace does not record hidden reasoning text.

## 7. Deterministic invariants

Unit/integration tests enforce the runtime properties directly:

```text
no eligible capability -> no tools sent to the main model
ineligible tool -> rejected before execution
assistant tool_call -> matching tool result id preserved
multiple tools in one round -> all results preserved
multi-round tool chain -> prior results available to later rounds
conversation id -> prior turn context recovered on next request
tool messages -> retained in conversation history
history trimming -> starts at a user boundary
```

These invariants do not depend on a probabilistic behavioral eval.

## 8. Behavioral acceptance

After deterministic runtime tests pass, the existing live smoke verifies the current local Qwen runtime against representative behavior.

```bash
cd server
make check
make down
make up
make eval-smoke
```

Then run the complete checkpoint:

```bash
make eval-strict
```

A behavioral failure must be classified using the trace. Runtime code that already satisfies its invariant is not redesigned to compensate for an unrelated model failure.
