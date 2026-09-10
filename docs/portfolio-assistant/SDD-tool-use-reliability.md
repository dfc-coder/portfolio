# SDD — Go-like reliable agent runtime

Status: implemented.

Branch: `feat/agent-live-eval`

## Objective

Keep the backend explicit, small and easy to reason about. Python owns control flow; Qwen owns natural-language interpretation inside bounded responsibilities.

## Runtime

```text
visitor
  -> ConversationStore
  -> Agent
      -> classify(message, context)
      -> run selected isolated workers
          general   tools=[]
          portfolio tools=[search_portfolio]
          temporal  tools=[resolve_datetime, set_reminder_mock]
      -> compose worker answers deterministically
  -> SSE
```

One physical model is used initially:

```text
llama.cpp
Qwen3.5-4B
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

## Invariants

1. `classify()` classifies only; it never executes tools or answers the visitor.
2. A worker never changes domain.
3. General receives no tools.
4. Portfolio receives only `search_portfolio`.
5. Temporal receives only `resolve_datetime` and `set_reminder_mock`.
6. There is one generic bounded model/tool loop in `app/worker.py`.
7. Tool names and arguments are validated before execution.
8. Tools never call the model.
9. Workers never communicate with each other.
10. Mixed-route composition is deterministic and does not call another model.
11. All model-facing prompts are English.
12. Final answers preserve the visitor language.
13. Successful duplicate tool calls within a turn are reused rather than executed twice.
14. Tool rounds are bounded.
15. Embeddings are retrieval infrastructure only; they never route or select tools.
16. No supervisor, critic, planner, graph, reranker, semantic tool search or agent framework.

## Tool registry

Production tools:

```text
search_portfolio
resolve_datetime
set_reminder_mock
```

`app/tools.py` owns each schema, handler and validation path. A worker receives an explicit tuple of allowed schemas. Adding a tool does not change the generic worker loop.

## Model/tool protocol

For a tool round:

```text
assistant tool_calls
  -> validate allowed name
  -> validate arguments
  -> execute sequentially
  -> append matching tool result
  -> next model round
```

Only final text from a round without tool calls is exposed to the visitor.

## Conversation state

The server stores complete OpenAI-compatible history, including assistant tool calls and matching tool results. History is bounded and trimmed at a user-message boundary.

## Acceptance

The runtime is accepted only when deterministic tests and behavioral evals pass without weakening expectations:

```bash
make check
make eval-regression
make eval-smoke
```

`make eval-strict` is the larger optional gate.

A behavioral failure is treated as a model/schema/prompt issue first. Do not add new routing layers or helper intelligence merely to hide a failing eval.
