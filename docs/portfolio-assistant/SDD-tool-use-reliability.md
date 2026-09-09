# SDD — Go-like 4B temporal fast path

Status: Design approved for implementation. M0 measured; M1–M5 pending.

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
- model-facing prompts remain English;
- visitor-facing answers preserve the visitor language.

The first optimization scope is only the temporal path. `general` and `portfolio` remain behaviorally unchanged so performance changes can be measured independently.

## 2. M0 — Freeze the 4B baseline

The reference model for this milestone is the local model that produced the first complete smoke pass:

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

The important performance baseline for the current temporal worker is also recorded:

```text
first tool round prompt     ~1067–1082 tokens
cached prefix               ~551 tokens
model calls per temporal request
  1 classifier
  1 tool-call generation
  1 final-answer generation
```

M0 rule: do not tune the model, sampling, quantization, or llama.cpp runtime while implementing M1–M4. Change one architectural variable at a time.

## 3. Current temporal path

Today the dispatcher exposes one broad temporal domain:

```text
visitor
  -> classify()
  -> temporal
  -> TemporalWorker
       tools:
         resolve_datetime
         set_reminder_mock
  -> native llama.cpp tool-call protocol
  -> Python executes selected tool
  -> model receives tool result
  -> model generates final answer
```

The model therefore receives two tool schemas plus llama.cpp's native tool-call instructions and grammar even when only one operation is possible from the user's intent.

The second model round exists only to turn an already deterministic tool result into visitor-facing prose.

## 4. Target architecture

```text
visitor
  -> classify()
       |
       +-> general   -> existing GeneralWorker
       |
       +-> portfolio -> existing PortfolioWorker + native search_portfolio tool
       |
       +-> datetime  -> structured DateTime request
       |                -> validate
       |                -> resolve_datetime() directly
       |                -> deterministic formatter
       |
       +-> reminder  -> structured Reminder request
                        -> validate
                        -> set_reminder_mock() directly
                        -> deterministic formatter

  -> compose worker results
  -> final response
```

For `datetime` and `reminder`, native tool calling disappears completely.

The model still performs the difficult NLP step:

```text
natural language -> structured semantic arguments
```

Python owns everything after that boundary:

```text
validate -> execute -> format -> return
```

## 5. M1 — Split `temporal` into `datetime` and `reminder`

### 5.1 Route contract

`Route` becomes:

```python
class Route(StrEnum):
    GENERAL = "general"
    PORTFOLIO = "portfolio"
    DATETIME = "datetime"
    REMINDER = "reminder"
```

`TEMPORAL` is removed.

The classifier remains a narrow structured classifier and still returns only:

```json
{"routes":["datetime"]}
```

or, for a genuine mixed request:

```json
{"routes":["portfolio","datetime"]}
```

### 5.2 Classification rules

`datetime` means a read-only date/time/weekday/timezone question.

`reminder` means the visitor explicitly asks to create a reminder.

A reminder that contains a relative time such as `in two hours` is still only `reminder`; it does not require an additional `datetime` route because the reminder operation resolves its own temporal reference.

If a visitor genuinely asks for both operations, for example "What date is tomorrow and remind me tomorrow to call Ana", the classifier may return both routes.

Conversational framing does not create an additional route.

### 5.3 M1 invariant

The dispatcher decides only the domain. It never creates tool arguments and never executes an operation.

## 6. M2 — Structured workers without native tool schemas

The `datetime` and `reminder` workers become semantic parsers.

They receive:

```text
small system prompt
recent conversation context when required
visitor message
```

They do **not** receive:

```text
OpenAI tool schemas
llama.cpp tool-call instructions
native tool-call grammar
unrelated tool descriptions
```

### 6.1 DateTime contract

The model returns one closed JSON object:

```json
{
  "kind": "date",
  "reference": "now",
  "offset": 1,
  "unit": "weeks",
  "timezone": null,
  "language": "es"
}
```

Runtime type:

```python
@dataclass(frozen=True)
class DateTimeRequest:
    kind: str
    reference: str
    offset: int
    unit: str
    timezone: str | None
    language: str
```

Allowed `kind` values:

```text
date
weekday
datetime
```

Allowed `unit` values remain:

```text
minutes
hours
days
weeks
```

### 6.2 Reminder contract

The model returns:

```json
{
  "reference": "now",
  "offset": 30,
  "unit": "minutes",
  "message": "Revisar el portfolio",
  "timezone": null,
  "language": "es"
}
```

Runtime type:

```python
@dataclass(frozen=True)
class ReminderRequest:
    reference: str
    offset: int
    unit: str
    message: str
    timezone: str | None
    language: str
```

### 6.3 Validation

Python validates the JSON before execution.

Invalid JSON, missing fields, unknown enum values, invalid timezone, invalid integer ranges, or unexpected fields fail explicitly. The worker never silently repairs its own output in code.

There is no temporal NLP parser, sklearn classifier, reranker, or regex semantic correction in M2.

The 4B remains the semantic authority for mapping natural language to these fields.

### 6.4 Worker implementation rule

Do not add a worker class hierarchy.

The implementation should remain data plus small functions. If shared JSON completion/parsing logic is needed, use one small helper rather than `BaseWorker`, `TemporalWorker`, `DateTimeAgent`, or similar abstractions.

## 7. M3 — Execute the operation directly from Python

After a structured request is validated, Python calls the existing deterministic operation directly.

Datetime:

```python
result = resolve_datetime(
    reference=request.reference,
    offset=request.offset,
    unit=request.unit,
    timezone=request.timezone,
)
```

Reminder:

```python
result = set_reminder_mock(
    reference=request.reference,
    offset=request.offset,
    unit=request.unit,
    message=request.message,
    timezone=request.timezone,
)
```

These functions already exist in `app/tools.py` and remain the source of truth for temporal execution.

The fast path does not synthesize:

```text
tool_call_id
assistant.tool_calls
tool role messages
OpenAI native tool envelopes
```

Those protocol objects are only necessary when the model itself is choosing/executing a native tool loop.

`search_portfolio` keeps the existing native tool path in this milestone.

### 7.1 M3 invariant

A structured temporal worker can propose arguments but cannot execute anything. Only the orchestrator/runtime calls the Python operation after validation.

## 8. M4 — Deterministic temporal responses

The temporal operation result is already deterministic. Do not invoke Qwen a second time only to paraphrase it.

Add two small formatting boundaries:

```python
render_datetime(request, result) -> str
render_reminder(request, result) -> str
```

The formatter is normal application code. It receives only validated structured data.

Examples:

```text
DateTimeRequest(kind="weekday", language="es")
+ weekday_es="jueves"
-> "Fue jueves."
```

```text
ReminderRequest(language="es")
+ status="simulated_only"
-> response that explicitly states the reminder is simulated/non-persistent
```

The first deterministic formatter scope is the languages currently exercised by the local acceptance suite: Spanish and English.

No LLM call is permitted after `resolve_datetime()` or `set_reminder_mock()` on this fast path.

### 8.1 Conversation state

The temporal fast path stores the visitor message and final assistant answer in normal conversation history.

Structured parser output and operation results belong in diagnostics/trace, not as synthetic OpenAI tool messages in conversation state.

This keeps runtime state independent from a wire protocol that is no longer used for these routes.

## 9. Composition

Each route still returns one `WorkerResult` to the orchestrator.

For a single route, return its formatted answer directly.

For multiple routes, keep the current deterministic composition behavior: concatenate route results in dispatch order. Do not introduce a merger LLM.

Workers never communicate with each other.

## 10. Tracing

Temporal traces must expose enough information to compare correctness and performance without exposing hidden reasoning.

Record:

```text
route
model name
structured raw output
parsed request
validation status
operation name
operation result
parser prompt tokens
parser completion tokens
parser latency
operation latency
formatter latency
total request latency
```

Native `tool_call_id` fields are not expected for the `datetime` and `reminder` fast paths.

## 11. Expected file changes

Keep the change small and flat.

```text
server/app/dispatcher.py
  temporal -> datetime + reminder

server/app/prompt.py
  update classifier domains
  replace TEMPORAL_PROMPT with compact DATETIME_PROMPT and REMINDER_PROMPT

server/app/agent.py
  register/dispatch the two new routes
  call structured temporal path
  keep general/portfolio behavior unchanged

server/app/worker.py
  retain existing worker loop for native-tool workers
  add only the minimum structured-completion helper if needed

server/app/tools.py
  keep resolve_datetime() and set_reminder_mock() as execution source of truth
  no semantic parsing added here

server/tests/
  add deterministic route/contract/execution/formatter tests

server/tests/evals/
  keep existing smoke expectations unchanged
```

A new module such as `app/temporal.py` is acceptable only if the structured contracts, validators, and formatters would otherwise make `agent.py` or `worker.py` harder to read. It must remain one focused module, not a package hierarchy.

## 12. M5 — Acceptance gate

M5 runs after M1–M4 are complete.

Correctness gate:

```text
make check            PASS
make eval-regression  4/4
make eval-smoke      10/10

tool/operation selection  10/10
argument extraction         8/8
tool execution             10/10
answers present            10/10
```

The existing eval cases must not be weakened, renamed, or rewritten to make the new architecture pass.

Structural gate:

```text
datetime worker native tools       0
reminder worker native tools       0
model calls per temporal request   2
  classifier                       1
  structured parser                1
post-operation LLM calls           0
```

Performance gate:

```text
baseline p50       ~31.17 s
target p50         <= 23.4 s   # at least 25% improvement
```

`p95` must be recorded but is not a hard gate in M5 because the baseline contains large runtime variance/outliers. It becomes a hard target only after CPU/runtime stability is measured separately.

Prompt-size target for the first temporal model call:

```text
current     ~1067–1082 tokens
target      <= 500 tokens
```

If correctness drops below `10/10`, the optimization is rejected regardless of latency improvement.

## 13. Implementation sequence

```text
M0  record baseline and do not change runtime tuning
M1  split temporal routing
    -> deterministic classifier tests

M2  introduce DateTimeRequest / ReminderRequest
    -> structured-output parser tests
    -> prove no native temporal tool schemas are sent

M3  direct Python execution
    -> validation + operation tests

M4  deterministic formatting
    -> prove no second temporal LLM completion occurs

M5  run regression and complete smoke
    -> compare correctness, prompt tokens, model-call count, p50 and p95
```

Each milestone must leave the server runnable. Do not land disconnected components for a later milestone.

## 14. Architectural invariants

```text
classifier never executes operations
classifier never answers the visitor
workers never communicate with each other
general has no tools
portfolio keeps only portfolio capability
datetime cannot create reminders
reminder cannot perform portfolio retrieval
temporal fast-path workers receive no native tool schemas
structured output is validated before execution
tools never call the model
Python owns execution and termination
no second LLM call after deterministic temporal execution
one physical Qwen3.5-4B instance initially
all model-facing prompts are English
visitor-facing output preserves visitor language
no reranker or embeddings participate in routing
```

## 15. Rollback rule

M0 is the rollback point.

If M5 cannot keep `10/10`, revert M1–M4 as one optimization set and keep the current working 4B architecture. Do not compensate for a regression by adding semantic special cases, extra agents, a reranker, or another model inside this milestone.

The optimization thesis is deliberately narrow:

> Keep the model that is already correct. Remove protocol work the application does not need.
