# Portfolio Assistant

The assistant answers portfolio/CV questions through a minimal bounded multi-tool loop.

```text
visitor
  -> API
  -> Agent
      -> Qwen
      -> tool_calls?
          -> execute requested tools
          -> append assistant tool_calls + matching tool results
          -> repeat
      -> final answer
```

Available tools:

```text
search_portfolio
get_current_datetime
add_duration_to_datetime
set_reminder_mock
```

Tool schemas are explicit OpenAI-compatible JSON. Python performs small explicit runtime validation. Assistant `tool_calls` and tool results are preserved with matching `tool_call_id` values so Qwen can continue dependent tool chains correctly.

The backend is stateless. The browser round-trips a bounded hidden OpenAI-compatible conversation context across HTTP turns. There is no planner, graph, registry, scheduler, calendar integration, persistent reminder service, or server-side conversation store.

Qwen thinking mode is disabled. Operational model execution is reported as `model`; it is not exposed as model reasoning. `set_reminder_mock` remains a stateless simulation used to exercise the multi-round tool flow safely.
