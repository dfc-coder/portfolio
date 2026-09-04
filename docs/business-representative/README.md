# Portfolio Assistant

Current scope: answer questions about Diego Cano's portfolio and CV.

```text
visitor → API → PortfolioAgent → OpenAI SDK → llama.cpp/Qwen → response
                         ↓
                    profile retrieval
```

The browser sends the visible conversation history with each request. The server keeps no conversation state.

There is no scheduling, calendar, action execution, planner, router, tool framework, custom model client or custom embedding client.

The profile JSON is the factual source. The production prompt defines response behavior.
