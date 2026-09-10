# Portfolio Assistant

The backend is a small local portfolio/CV agent with a Go-like runtime: explicit control flow, bounded state, simple tool registration, and no semantic routing framework.

## Runtime

```text
FastAPI / SSE
  -> ConversationStore
  -> Agent
      -> llama.cpp / Qwen3.5-2B-Q6_K
      -> registered tool schemas
      -> explicit bounded tool loop
```

The model decides whether a tool is needed. The server validates registered names and arguments, executes calls in order, preserves `tool_call_id`, and reuses successful identical calls instead of executing them twice.

There is no capability gate, ToolSearch, reranker, planner, graph, or agent framework.

## Local model

```text
unsloth/Qwen3.5-2B-GGUF
Qwen3.5-2B-Q6_K.gguf
```

Portfolio retrieval continues to use `Qwen3-Embedding-0.6B` as infrastructure for `search_portfolio`; embeddings do not select tools.

## Documents

- `SDD-tool-use-reliability.md` — runtime architecture and invariants.
- `TRACE.md` — diagnostic trace contract.
- `../../server/README.md` — local run and file layout.
