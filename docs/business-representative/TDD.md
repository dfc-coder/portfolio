# TDD — Acceptance and regression suite

Executable tests live in `server/tests` and focus on the behavior that matters after the explicit-capability refactor.

## Current regression surface

1. Semantic routing selects only `CONVERSATION`, `PORTFOLIO` or `SCHEDULING` without a reranker or LLM judge.
2. Static route embeddings are cached instead of recomputed per turn.
3. `PortfolioSearch` caches profile document embeddings instead of recomputing them per turn.
4. `PortfolioSearch` returns concrete `Fact` values with a source.
5. Evidence below the configured minimum score is not returned as supported portfolio knowledge.
6. Follow-up retrieval uses recent visitor turns and excludes previous assistant text.
7. `Responder` receives supplied evidence and does not own retrieval.
8. Portfolio interruptions preserve active scheduling memory.
9. Scheduling relation is derived by the scheduling consumer rather than encoded as a router dispatch decision.
10. A supplied date causes availability lookup without a conversation-stage machine.
11. Details supplied before slot selection are preserved.
12. A pending booking cannot write to Calendar from free-form chat confirmation alone.
13. An unrecognized scheduling turn does not silently fall through to another capability.
14. Explicit UI approval creates exactly one Calendar booking.
15. General and portfolio responses use the real LLM stream path.
16. The stream guard catches unverified completed Calendar claims split across chunks.
17. The FastAPI endpoint preserves the SSE ready/token/done contract.
18. Slot calculation respects busy intervals, business hours and buffers.

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
active scheduling + professional question -> PORTFOLIO -> PortfolioSearch -> Responder
active scheduling + meeting detail -> SCHEDULING -> Scheduler
portfolio follow-up -> retrieval from visitor turns only
unsupported portfolio claim -> zero facts -> abstention prompt
slots offered + slot selection -> selected offered slot only
pending booking + chat text -> no Calendar write
pending booking + explicit UI approval -> one Calendar write
"Hola" -> CONVERSATION
"¿cuánto cobra por hora?" -> PORTFOLIO
```

Live-model evaluation remains separate from the deterministic regression suite.
