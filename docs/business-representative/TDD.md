# TDD — Acceptance and regression suite

Executable tests live in `server/tests` and focus on the behavior that matters after the KISS refactor.

## Current regression surface

1. Semantic routing selects the highest-similarity route without a reranker or LLM judge.
2. Static route embeddings are cached instead of recomputed per turn.
3. Static business-profile embeddings are cached instead of recomputed per turn.
4. Business retrieval sends only the top dense matches into the response context.
5. Recent turns are included in the retrieval query so short follow-ups retain their referent.
6. Business interruptions preserve active scheduling memory.
7. A false scheduling route can return `not_applicable` and fall back to business/general.
8. A supplied date causes availability lookup without a conversation-stage machine.
9. Details supplied before slot selection are preserved.
10. A slot that was not offered is rejected.
11. A pending booking cannot write to Calendar from free-form chat confirmation alone.
12. Explicit UI approval creates exactly one Calendar booking.
13. Business/general responses use the real LLM stream path.
14. The stream guard catches completed Calendar claims split across chunks.
15. Capability descriptions remain streamable.
16. The FastAPI endpoint preserves the SSE ready/token/done contract.
17. Slot calculation respects busy intervals, business hours and buffers.

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
active scheduling + professional question -> business interrupt
active scheduling + meeting detail -> scheduling continuation
slots offered + slot selection -> selected offered slot only
pending booking + chat text -> no Calendar write
pending booking + explicit UI approval -> one Calendar write
"Hola" -> general
"¿cuánto cobra por hora?" -> business
```

Live-model evaluation remains separate from the deterministic regression suite.
