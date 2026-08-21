# TDD — Acceptance and regression suite

Executable tests live in `server/tests` and focus on semantic routing, belief preservation, capability applicability, bounded execution, side-effect safety, and real SSE streaming.

## Current regression surface

1. Semantic routing uses the reranker directly when the winner is clear.
2. Ambiguous routing escalates to the constrained Qwen judge.
3. An active scheduling task can be interrupted by a business question without losing scheduling belief.
4. A false scheduling route can return `not_applicable`, reroute to business/general, and avoid running the scheduling loop.
5. Date facts make calendar availability search eligible without any conversation-stage enum.
6. Pending booking alone is insufficient to make a Calendar write eligible; explicit confirmation is required.
7. Details supplied while waiting for a slot are preserved and the already-offered slots remain actionable.
8. A slot not previously offered is rejected by the deterministic safety gate.
9. Scheduling can execute a bounded multi-step turn: select slot -> prepare pending booking.
10. Calendar writes do not occur before explicit confirmation.
11. Explicit confirmation creates exactly one booking in the end-to-end scheduling flow.
12. Business/general answers use the real LLM stream path.
13. The streaming output guard detects restricted claims across chunk boundaries.
14. The FastAPI endpoint preserves the SSE ready/token/done contract.
15. Slot generation removes busy periods and applies configured scheduling policy.

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

Keep hard negatives and multi-turn examples for semantic interpretation, including:

```text
active scheduling + "¿Tenés herramientas?" -> business interrupt
active scheduling + "mañana" -> scheduling inform
slots offered + "el segundo" -> scheduling select
pending booking + "sí, eso me interesa" -> not an explicit write confirmation
pending booking + "sí, confirmo" -> confirm
"¿qué hora es?" -> general
"¿cuánto cobra por hora?" -> business
```

These examples are evaluation data first. They should not be treated as statistically calibrated classifier training data until enough reviewed real conversations exist.

## Next tests before production traffic

- capability selector ambiguity against the real reranker service;
- interpreter golden-case accuracy against the deployed Qwen3.5-0.8B quantization;
- maximum-step and maximum-repair exhaustion;
- duplicate/idempotent Calendar-write protection;
- Google OAuth token refresh with mocked HTTP transport;
- Calendar HTTP conflict/retry behavior;
- session expiration with stale pending booking;
- queue latency/load test with llama.cpp `--parallel 1`;
- browser E2E test for SSE disconnect/reconnect behavior;
- classifier shadow-mode accuracy/calibration once a reviewed dataset exists.
