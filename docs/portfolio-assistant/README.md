# Portfolio Assistant

Current backend design: explicit Go-like orchestration around one llama.cpp `Qwen3.5-4B` instance.

```text
classifier
  -> general worker      tools=[]
  -> portfolio worker    tools=[search_portfolio]
  -> temporal worker     tools=[resolve_datetime, set_reminder_mock]
      -> one generic bounded tool loop
```

No supervisor, planner, critic, graph, reranker, semantic tool search or framework-managed agents.

Documents:

- `BDD-agent-runtime-minimo.md` — requerimientos BDD para simplificar el agent runtime.
- `SDD-agent-runtime-minimo.md` — diseño propuesto para implementar el runtime mínimo, incluido streaming final token por token.
- `SDD-tool-use-reliability.md` — current runtime contract and invariants.
- `TRACE.md` — observable diagnostic trace.
- `../../server/README.md` — local runtime and validation commands.
