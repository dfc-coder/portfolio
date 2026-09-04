# Portfolio Assistant

Current scope: answer questions about Diego Cano's portfolio and CV.

The runtime is intentionally limited to retrieval and response generation:

```text
visitor → API → PortfolioAgent → PortfolioSearch → prompt → Qwen → response
```

There is no scheduling, calendar integration, action execution, planner, tool registry, router or agent graph in the current product.

The profile JSON is the factual source. The production prompt defines response behavior. Python owns transport, short conversation history, retrieval and model I/O.
