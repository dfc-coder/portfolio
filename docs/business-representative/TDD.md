# TDD — Acceptance and regression suite

Executable tests live in `server/tests` and focus on the knowledge-agent behavior that matters.

## Current regression surface

1. Static business-profile embeddings are cached instead of recomputed per turn.
2. Business retrieval sends only qualifying dense matches into the response context.
3. Experience questions retrieve professional-experience documents.
4. General no-match turns do not receive portfolio knowledge.
5. Recent visible turns remain available as conversational context.
6. Business/general responses use the real LLM stream path.
7. The stream guard blocks owner impersonation while preserving safe text.
8. The FastAPI endpoint preserves the SSE ready/token/done contract.
9. PocketTrace remains optional and disabled by default.
10. The architecture contains no semantic intent router, scheduling workflow or calendar integration.

## Local command

```bash
cd server
PYTHONPATH=. pytest -q
```

Or:

```bash
make check
```

## Representative cases

```text
"Hola" -> general
"¿qué experiencia tiene Diego?" -> grounded business response
"¿qué proyectos hizo en Rust?" -> grounded project response
"¿cuánto cobra por hora?" -> use configured profile boundary; do not invent a rate
```
