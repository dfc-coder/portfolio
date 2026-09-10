# Portfolio Assistant

Diseño objetivo del backend: un runtime explícito y Go-like alrededor de una única instancia de `Qwen3.5-4B`.

```text
visitor
  -> Agent
      -> Qwen + [search_portfolio, resolve_datetime, set_reminder_mock]
      -> final answer: stream token by token
      -> tool call: execute -> tool result -> next model round
```

No classifier, routes, workers, supervisor, planner, critic, graph, reranker, semantic tool search ni framework de agentes.

Documentos vigentes:

- `BDD-agent-runtime-minimo.md` — qué comportamiento debe conservar el runtime.
- `SDD-agent-runtime-minimo.md` — cómo se implementa el runtime mínimo y el streaming final.
- `DOD-agent-runtime-minimo.md` — gates obligatorios para considerar terminado el cambio.
- `TRACE.md` — contrato de diagnóstico observable del runtime mínimo.
- `../../server/README.md` — ejecución y validación local.
