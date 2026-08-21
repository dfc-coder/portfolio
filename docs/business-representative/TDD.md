# TDD — Acceptance and regression suite

Executable tests live in `server/tests` and focus on the behavior that still matters after the KISS refactor.

## Current regression surface

1. Clear semantic routes use the reranker without calling the Qwen routing judge.
2. Ambiguous routes escalate to the constrained Qwen judge.
3. Business interruptions preserve active scheduling memory.
4. A false scheduling route can return `not_applicable` and fall back to business/general.
5. A supplied date causes availability lookup without a conversation-stage machine.
6. Details supplied before slot selection are preserved.
7. A slot that was not offered is rejected.
8. A pending booking is not written on ambiguous agreement.
9. Explicit confirmation creates exactly one Calendar booking.
10. Business/general responses use the real LLM stream path.
11. The stream guard catches completed Calendar claims split across chunks.
12. Capability descriptions such as "I can schedule after confirmation" remain streamable.
13. The FastAPI endpoint preserves the SSE ready/token/done contract.
14. Slot calculation continues to respect busy intervals, business hours and buffers.

## Local command

```bash
cd server
PYTHONPATH=. pytest -q
```

Or:

```bash
make check
```

## Golden cases to grow with real traffic

```text
active scheduling + "¿Tenés herramientas?" -> business interrupt
active scheduling + "mañana" -> scheduling continuation
slots offered + "el segundo" -> select S2
pending booking + "Tuesday could work" -> no write
pending booking + "sí, confirmo" -> write
"¿qué hora es?" -> general
"¿cuánto cobra por hora?" -> business
```

These remain evaluation cases first. They are not a calibrated classifier dataset.

## Next tests before production traffic

- scheduling extraction accuracy against the deployed Qwen3.5-0.8B quantization;
- capability-aware response quality against the real model;
- duplicate/idempotent Calendar-write protection;
- Google OAuth token refresh with mocked HTTP transport;
- Calendar conflict/retry behavior;
- session expiration with stale pending booking;
- queue latency/load test with llama.cpp `--parallel 1`;
- browser E2E test for SSE disconnect/reconnect;
- classifier shadow-mode accuracy/calibration once enough reviewed data exists.
