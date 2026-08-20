# SDD — Server-side Business Representative

## 1. Context

The existing Vue `AgentOS` already separates rendering from an `AgentProvider`. The new system keeps that UI contract and replaces the regex/local provider with a remote provider. The model never executes in the browser.

## 2. Deployment topology

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI Business Representative
     |
     +-- SessionStore (TTL, in-memory MVP)
     +-- SchedulingPolicy
     +-- SlotService
     +-- GoogleCalendarGateway ----> Google Calendar
     +-- LlamaClient
               |
               v
        llama-server
        Qwen3.5-2B Q4_K_XL
        --parallel 1
        --cache-prompt
        --jinja
        model resident in process memory
```

Netlify remains static hosting. FastAPI and llama-server must run on long-lived infrastructure (VM, container host or always-on service). A scale-to-zero/serverless inference host cannot guarantee permanent model residency.

## 3. Browser boundary

`businessAgentProvider.ts` is the only browser integration point. It sends:

```json
{
  "session_id": "web-<uuid>",
  "message": "visitor message"
}
```

To `POST /v1/chat/stream` and consumes SSE events:

```text
event: ready
data: {"session_id":"..."}

event: token
data: {"text":"..."}

event: done
data: {}
```

No model, tokenizer, embeddings or business secrets are shipped to the browser.

## 4. LLM serving

`llama-server` is configured with:

- Qwen3.5-2B GGUF, Q4_K_XL
- one slot: `--parallel 1`
- prompt cache: `--cache-prompt`
- idle slot cache enabled
- cache reuse enabled
- Jinja chat templates/tool calling enabled
- 8K context baseline
- thinking disabled through `chat_template_kwargs` for low latency

The FastAPI `LlamaClient` also uses an `asyncio.Semaphore(1)` so application concurrency matches the single inference slot instead of creating an uncontrolled queue.

## 5. Prompt/cache layout

The prompt is intentionally ordered for longest-common-prefix reuse:

```text
[stable system instructions]
[stable BUSINESS_CONTEXT]
[dynamic current time/timezone]
[bounded session turns]
[current tool result, when present]
```

The stable business prefix changes only when `business-profile.json` changes. Current time is placed after it so daily/time-specific values do not invalidate the full prefix.

## 6. Conversation strategy

This is not an unrestricted ReAct loop.

For ordinary business questions:

```text
visitor -> LlamaClient streaming -> SSE -> browser
```

For scheduling-intent messages:

```text
visitor
  -> one bounded tool-decision call
  -> execute at most one scheduling tool
  -> final streamed response
```

Exposed LLM tools:

1. `get_availability(start_date, end_date)`
2. `prepare_booking(slot_start, visitor_name, visitor_email, subject)`

`prepare_booking` is non-destructive. It only creates pending session state.

The destructive Calendar write is not an LLM tool. It is executed deterministically by FastAPI only when:

1. a pending booking exists;
2. its slot came from a prior availability result;
3. the next visitor message is an explicit confirmation.

## 7. Calendar integration

`GoogleCalendarGateway` uses server-side OAuth refresh credentials from environment variables.

Read path:

```text
POST https://www.googleapis.com/calendar/v3/freeBusy
```

Write path:

```text
POST https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events
```

Only free/busy intervals are passed back to the model. Event titles, attendee lists and unrelated calendar details are not exposed.

Each prepared booking receives a stable booking ID. The Calendar event ID is derived from that ID. A retry that receives HTTP 409 fetches the existing event rather than creating a second meeting.

## 8. Session model

MVP session state is server-side and TTL bounded:

```text
SessionState
  session_id
  turns[-N:]
  offered_slots
  pending_booking?
  last_booking_id?
  last_activity
```

Default TTL: 30 minutes. Default retained turns: 12.

A future multi-replica deployment should replace `SessionStore` with Redis without changing the agent API.

## 9. Business policy

Configured, not hardcoded in prompts:

- timezone
- meeting length
- buffer
- minimum notice
- maximum scheduling horizon
- business hours
- maximum proposed slots

The authoritative values live in `server/config/business-profile.json`.

## 10. Security boundaries

- Google OAuth credentials only exist in server environment variables.
- Browser receives no Calendar token.
- No direct Calendar write tool is exposed to the LLM.
- Booking requires explicit confirmation.
- A requested slot must exactly match a previously offered slot.
- API input is length- and shape-validated.
- CORS origins are configurable.
- Calendar failure never becomes a success claim.
- Production should add an edge rate limit / bot challenge before public launch.

## 11. Failure behavior

| Failure | Result |
|---|---|
| llama-server unavailable | SSE `error`; UI shows agent failure |
| model still loading | `/ready` reports degraded |
| bad tool arguments | tool returns structured error; no side effect |
| Calendar free/busy failure | no invented slots |
| Calendar event insert failure | user is told nothing was booked |
| browser refresh | session survives within `sessionStorage`; backend state survives until TTL/process restart |

## 12. Scale path

Current target is deliberately one model slot. When observed queue latency becomes unacceptable:

1. move session state to Redis;
2. increase llama.cpp slots if memory permits, or switch the OpenAI-compatible backend to vLLM/SGLang;
3. preserve the FastAPI and Vue contracts.

No frontend rewrite is required for that evolution.
