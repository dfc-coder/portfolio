# Portfolio Assistant

Current scope: answer portfolio/CV questions and exercise a minimal multi-tool agent loop.

```text
visitor
  -> API
  -> Agent
      -> Qwen
      -> tool_calls?
          -> search_portfolio
          -> get_current_datetime
          -> add_duration_to_datetime
          -> set_reminder_mock
      -> tool results
      -> repeat until final answer
```

The agent loop is explicit and bounded. OpenAI-compatible tool schemas describe each function, Pydantic validates generated arguments before execution, and each tool result is returned with its matching `tool_call_id`.

There is no planner, graph, registry, scheduler, calendar integration or persistent reminder service. `set_reminder_mock` is a stateless simulation used only to validate multi-round tool behavior.
