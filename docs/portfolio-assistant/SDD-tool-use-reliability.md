# SDD — Go-like 4B temporal fast path

Status: M0–M4 implemented; M5 pending local live smoke validation.

Branch: `feat/agent-live-eval`

## 1. Objective

Keep the correctness already demonstrated by `Qwen3.5-4B` while reducing the latency of temporal requests.

The optimization must preserve the Go-like runtime philosophy:

- control flow is owned by Python;
- the model interprets natural language, but does not own execution;
- every boundary has a small explicit contract;
- no agent framework, graph, planner, critic, reranker, or semantic tool search;
- no hidden worker-to-worker communication;
- no special-case parsing such as `if "semana" in text`;
- model-facing natural-language instructions remain English;
- visitor-facing answers preserve the visitor language.

The first optimization scope is only the temporal path. `general` and `portfolio` remain behaviorally unchanged so performance changes can be measured independently.

## 2. M0 — Frozen 4B baseline

Reference runtime:

```text
llama.cpp
Qwen3.5-4B
Qwen3.5-4B-UD-Q4_K_XL.gguf
thinking disabled
```

Reference smoke result:

```text
cases                  10/10
route/tool selection   10/10
argument extraction      8/8
tool execution         10/10
answers present        10/10
p50 latency          ~31.17 s
p95 latency          ~91.71 s
```

This result is the correctness baseline. M1–M4 are accepted only if M5 preserves `10/10`.

Performance baseline for the old temporal worker:

```text
first tool round prompt     ~1067–1082 tokens
cached prefix               ~551 tokens
model calls per temporal request
  1 classifier
  1 tool-call generation
  1 final-answer generation
```

M0 rule: do not tune sampling, quantization, or llama.cpp runtime while implementing M1–M4. Change one architectural variable at a time.

## 3. Target runtime

```text
visitor
  -> classify()
       |
       +-> general   -> existing GeneralWorker
       |
       +-> portfolio -> existing PortfolioWorker + native search_portfolio tool
       |
       +-> datetime  -> DateTimeRequest JSON contract
       |                -> strict validation
       |                -> resolve_datetime() directly
       |                -> deterministic formatter
       |
       +-> reminder  -> ReminderRequest JSON contract
                        -> strict validation
                        -> set_reminder_mock() directly
                        -> deterministic formatter

  -> compose worker results
  -> final response
```

For `datetime` and `reminder`, native tool calling disappears completely.

The model performs only the NLP step:

```text
natural language -> structured semantic arguments
```

Python owns everything after that boundary:

```text
validate -> execute -> format -> return
```

## 4. M1 — Split temporal routing

`Route` is:

```python
class Route(StrEnum):
    GENERAL = "general"
    PORTFOLIO = "portfolio"
    DATETIME = "datetime"
    REMINDER = "reminder"
```

`TEMPORAL` is removed.

The classifier returns a closed route list, for example:

```json
{"routes":["datetime"]}
```

or a genuine mixed request:

```json
{"routes":["portfolio","datetime"]}
```

Rules:

- `datetime` is a read-only date/time/weekday/timezone question;
- `reminder` means the visitor explicitly asks to create a reminder;
- a reminder containing a date or duration is still only `reminder` unless a separate date/time question exists;
- conversational framing does not create another route;
- the classifier never creates operation arguments and never executes an operation.

## 5. M2 — Schema-first temporal contracts

The datetime and reminder paths are semantic parsers, not native tool workers.

They receive a compact instruction, a closed JSON Schema contract, relevant plain conversation context, and the visitor message. They do not receive OpenAI native tool definitions, unrelated tool descriptions, or a tool-selection problem.

The schema is the source of truth for model-facing field semantics. Free-form temporal rules are not duplicated in `prompt.py`.

### DateTimeRequest

```python
@dataclass(frozen=True)
class DateTimeRequest:
    kind: str
    reference_kind: str
    reference: str
    offset: int
    unit: str
    timezone: str | None
    language: str
```

Model output example for an explicit date:

```json
{
  "kind": "weekday",
  "reference_kind": "date",
  "reference": "2026-12-25",
  "offset": 0,
  "unit": "days",
  "timezone": null,
  "language": "es"
}
```

Closed values:

```text
kind:           date | weekday | datetime
reference_kind: now | date | datetime
unit:           minutes | hours | days | weeks
```

Reference invariants:

```text
reference_kind=now
  reference must be exactly "now"

reference_kind=date
  reference must be exactly YYYY-MM-DD
  timezone must be null

reference_kind=datetime
  reference must be ISO-8601 and include a time
```

The important distinction is semantic, not cosmetic. A visitor-provided date without a time is represented as `reference_kind=date`; the model must not manufacture midnight, UTC, or a locale-derived timezone.

### ReminderRequest

```python
@dataclass(frozen=True)
class ReminderRequest:
    reference_kind: str
    reference: str
    offset: int
    unit: str
    message: str
    timezone: str | None
    language: str
```

Model output example:

```json
{
  "reference_kind": "now",
  "reference": "now",
  "offset": 30,
  "unit": "minutes",
  "message": "Revisar el portfolio",
  "timezone": null,
  "language": "es"
}
```

Both contracts use:

```text
required fields
closed enums
integer bounds
string length bounds
additionalProperties=false
short property descriptions
```

The runtime then performs explicit cross-field validation. It rejects inconsistent structures rather than silently rewriting model output.

There is no language-specific temporal parser, sklearn classifier, reranker, or regex-based semantic correction in this milestone.

## 6. M3 — Direct Python execution

After validation the orchestrator executes the existing deterministic operation directly:

```text
DateTimeRequest
  -> resolve_datetime(...)

ReminderRequest
  -> set_reminder_mock(...)
```

`reference_kind` is a parser contract field only. It is validated and then removed at the execution boundary; the existing tool functions keep their stable inputs.

The model does not choose an operation after routing. Python owns that mapping:

```text
datetime -> resolve_datetime
reminder -> set_reminder_mock
```

The production operation implementation remains in `app/tools.py`; the fast path does not duplicate date/reminder business logic.

For observability, direct executions are recorded in the same trace shape used by the live evals, with `direct=true`. This keeps tool selection, argument extraction, and execution metrics comparable with the M0 baseline without exposing native tool schemas to the model.

## 7. M4 — Deterministic presentation

A successful temporal operation is formatted by Python. There is no second LLM call after `resolve_datetime` or `set_reminder_mock`.

The formatter is intentionally narrow:

```text
DateTimeRequest + operation result -> visitor-facing date/time sentence
ReminderRequest + operation result -> simulated reminder confirmation
```

The reminder formatter must state that the reminder is simulated/non-persistent and does not send a real notification.

General and portfolio responses remain model-generated because they are open-ended language tasks.

## 8. Conversation state

The orchestrator owns conversation state. Temporal parsers are stateless.

The direct temporal fast path stores only the final user-visible conversation result. It does not invent synthetic native assistant/tool protocol messages for future model context.

The classifier may use recent plain user/assistant context to interpret follow-ups. If a follow-up asks only for information already present in the conversation, it should remain a no-operation general/context answer rather than re-executing a temporal operation.

## 9. Native tool loop

The bounded native tool loop in `app/worker.py` remains for `search_portfolio`.

Its existing invariants remain unchanged:

```text
registered tool names only
validated arguments
preserved tool_call_id
sequential deterministic execution
successful identical-call reuse
hard round limit
intermediate tool text not exposed
```

Datetime and reminder bypass this loop by design.

## 10. Tracing

Diagnostics must make the fast path visible rather than hiding it.

For a direct temporal execution the trace records:

```text
route
structured model request/response
operation name
parsed arguments
operation result
direct=true
latency
```

The existing live eval reader continues to observe `resolve_datetime` and `set_reminder_mock` through `rounds[].tool_calls`, so M0 and M5 metrics remain comparable.

## 11. Files

```text
app/agent.py       orchestrator and explicit route execution
app/dispatcher.py  closed route classification
app/worker.py      native general/portfolio worker runtime
app/temporal.py    temporal JSON schemas, typed contracts, validation and fast path
app/tools.py       operation implementations + native registry
app/prompt.py      classifier/general/portfolio prompts only
```

No new framework or service is introduced.

## 12. M5 — Acceptance gate

Run:

```bash
make check
make eval-temporal-fast
make eval-smoke
```

Required correctness:

```text
temporal-fast                   8/8
smoke                          10/10
tool/operation selection       10/10
argument extraction              8/8
tool execution                 10/10
answers present                10/10
```

Performance is compared against M0:

```text
M0 p50 ~31.17 s
M0 p95 ~91.71 s
```

The first target is at least a 25% p50 reduction:

```text
M5 p50 <= ~23.4 s
```

The optimization is rejected if correctness drops below 10/10, regardless of latency improvement.

## 13. Expected performance change

Old temporal request:

```text
classifier
+ native tool-call model round with ~1k-token prompt
+ deterministic Python operation
+ final-answer model round
```

New temporal request:

```text
classifier
+ compact schema-guided semantic-parser round
+ strict Python validation
+ deterministic Python operation
+ deterministic formatter
```

Expected invariants:

```text
native temporal tool schemas      0
post-operation LLM calls           0
temporal LLM calls total           2  # classifier + parser
```

The optimization deliberately targets architectural token/work reduction before llama.cpp thread, batch, GPU, or quantization tuning.
