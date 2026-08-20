# TDD — Acceptance and regression suite

The first vertical slice is driven by executable tests in `server/tests`.

## Tests implemented

1. Explicit booking confirmation is narrower than ordinary agreement.
2. Scheduling intent is detected in English and Spanish.
3. Slot generation removes busy periods and applies the configured buffer.
4. Calendar writes do not occur before explicit confirmation.
5. Booking preparation rejects a slot that was not previously offered.
6. The FastAPI endpoint emits the expected SSE contract.

## Local command

```bash
cd server
PYTHONPATH=. pytest -q
```

Expected baseline:

```text
6 passed
```

## Next tests before production traffic

- Google OAuth token refresh with mocked HTTP transport.
- Calendar HTTP 409 idempotency path.
- llama.cpp tool-call parsing against the exact Qwen3.5-2B GGUF/chat template selected for deployment.
- CORS production-origin test.
- session expiration and stale pending-booking test.
- queue latency/load test with `--parallel 1`.
- browser E2E test for SSE disconnect/reconnect behavior.
