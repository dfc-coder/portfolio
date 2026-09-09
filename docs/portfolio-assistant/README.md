# Portfolio Assistant

The backend is a small local portfolio/CV agent with a Go-like runtime: explicit control flow, bounded state, structured semantic parsing, and no agent framework.

## Runtime

```text
FastAPI / SSE
  -> ConversationStore
  -> Agent / orchestrator
      -> llama.cpp / Qwen3.5-4B
      -> classify: general | portfolio | datetime | reminder
      -> general: no tools
      -> portfolio: native search_portfolio tool loop
      -> datetime/reminder: structured JSON -> validate -> direct Python operation -> deterministic formatter
```

The model interprets natural language. Python owns routing, validation, execution, termination, and deterministic temporal presentation.

`datetime` and `reminder` do not receive native tool schemas and do not make a second LLM call after execution. `search_portfolio` keeps the bounded native tool loop because retrieval still requires model-selected evidence.

There is no capability gate, ToolSearch, reranker, planner, supervisor, critic, graph, or agent framework.

## Local model

```text
unsloth/Qwen3.5-4B-GGUF
Qwen3.5-4B-UD-Q4_K_XL.gguf
```

The frozen pre-optimization 4B baseline passed the 10-case smoke gate at 10/10. M0–M4 are implemented; M5 is the local live acceptance gate and must preserve 10/10 while reducing latency.

Portfolio retrieval continues to use `Qwen3-Embedding-0.6B` as infrastructure for `search_portfolio`; embeddings do not route requests or select tools.

## Validation

```bash
make check
make eval-temporal-fast
make eval-smoke
```

`make eval-temporal-fast` isolates the eight datetime/reminder smoke cases. `make eval-smoke` remains the M5 acceptance gate.

## Documents

- `SDD-tool-use-reliability.md` — runtime architecture, M0–M5 fast-path design, and invariants.
- `TRACE.md` — diagnostic trace contract.
- `../../server/README.md` — local run, tests, and file layout.
