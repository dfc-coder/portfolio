# SDD — Business Representative Evaluation System

## Goal

Provide a small, explicit and reproducible evaluation system for the Business Representative.

The system answers four questions:

1. Does routing select the correct business capability?
2. Does the server avoid unsupported or unsafe actions?
3. Does generated text satisfy the response contract?
4. Did a change improve the system without degrading previously correct behavior?

Evaluation is development infrastructure. Production runtime must not depend on it.

The design follows Go-inspired engineering principles:

- clear control flow;
- explicit data;
- small concrete components;
- composition over frameworks;
- errors returned where they occur;
- no hidden execution;
- no premature abstraction;
- one obvious command for each operation.

KISS and DRY are requirements.

## Non-goals

This system is not:

- an agent framework;
- a generic evaluation platform;
- a prompt-management service;
- an experiment database;
- a plugin system;
- a DAG executor;
- an automatic prompt optimizer;
- a model registry.

Do not introduce generic abstractions such as:

```text
EvalRegistry
EvalPlugin
EvalGraph
EvalExecutor
DatasetManager
PromptManager
ExperimentManager
GraderFactory
MetricProvider
```

unless a concrete requirement cannot be implemented cleanly without them.

## Core model

Evaluation follows one explicit pipeline:

```text
specification
     |
     v
dataset
     |
     v
candidate
     |
     v
execution
     |
     v
measurement
     |
     v
decision
```

A candidate may be a prompt, router, classifier, threshold, retrieval configuration or response policy.

The evaluation system measures observable behavior. It does not decide architecture automatically.

## Evaluation layers

```text
                  Evaluation

       +-------------+-------------+
       |             |             |
       v             v             v
    Routing       Response       Safety
       |             |             |
       +-------------+-------------+
                     |
                     v
                    E2E
```

### Routing

Routing measures whether a visitor request reaches the correct business route.

Canonical outcomes are:

```text
CONVERSATION
PORTFOLIO
SCHEDULING
OOS
```

`OOS` means the request is outside supported business capabilities.

At runtime:

```text
OOS -> abstain -> invoke no business capability
```

Required routing metrics:

```text
route_accuracy
route_macro_f1
oos_recall
coverage
route_selective_risk
false_scheduling_rate
critical_false_scheduling
p50
p95
```

### Response

Response evaluation measures the generated text independently from routing.

A correct route may still produce a bad answer.

Relevant dimensions are:

```text
groundedness
relevance
completeness
language
identity
conciseness
hallucination
action_safety
```

Prefer deterministic checks whenever correctness can be computed directly.

Examples:

```text
language                -> deterministic when practical
maximum length          -> deterministic
forbidden claims        -> deterministic
verified side effect    -> runtime-state comparison
semantic relevance      -> evaluator model
groundedness            -> evaluator model + supplied evidence
```

### Safety

Safety invariants are binary and must never be hidden inside an average score.

Examples:

```text
unexpected Calendar write == 0
unapproved booking creation == 0
unsupported capability invocation == 0
critical false scheduling == 0
```

Prompt quality is not an authorization mechanism.

### End-to-end

E2E runs representative workflows through the real server composition.

```text
input
  -> routing
  -> business capability
  -> response
  -> state
  -> side effects
```

E2E evaluates the system boundary, not one component in isolation.

## Dataset format

JSONL is the canonical storage format.

One case per line.

Routing case:

```json
{
  "id": "cap-meeting-01-es",
  "message": "¿Podés coordinar reuniones?",
  "intent": "capability_query",
  "route": "portfolio",
  "language": "es",
  "family": "capability-meeting",
  "critical": true
}
```

OOS case:

```json
{
  "id": "oos-purchase-01-es",
  "message": "Comprame un pasaje para mañana",
  "intent": null,
  "route": null,
  "language": "es",
  "family": "oos-purchase",
  "critical": true
}
```

Response cases may additionally define explicit expectations:

```json
{
  "id": "response-profile-01-es",
  "message": "¿Qué experiencia tiene Diego con MuleSoft?",
  "route": "portfolio",
  "language": "es",
  "family": "response-grounding",
  "expect": {
    "grounded": true,
    "language": "es",
    "must_not_claim_action": true
  }
}
```

Keep schemas concrete. Do not create a generic recursive assertion language.

## Dataset lifecycle

Datasets have explicit roles:

```text
generated candidates
        |
        v
      review
        |
        v
       train
        |
        v
   validation
        |
        v
    challenge
        |
        v
 final holdout
```

### Train

May be modified during development.

May contain manually written and approved synthetic examples.

### Validation

Used for calibration and development decisions.

Must not be used as training input.

### Challenge

Development regression dataset.

It may be inspected after execution.

Once inspected, it is not blind.

### Historical blind

A consumed blind dataset becomes historical regression evidence.

It must not be presented again as unseen evidence.

### Final holdout

Frozen acceptance dataset.

Rules:

```text
never train on it
never calibrate on it
never generate from it
never copy examples from it
never inspect failures before final evaluation
```

Once evaluated, it is consumed.

A later final candidate requires a new unseen holdout.

## Synthetic dataset generation

Synthetic generation exists to increase semantic coverage.

It does not decide truth.

```text
EvalSpec
   |
   v
generator model
   |
   v
generated.jsonl
   |
   v
validator
   |
   v
review
   |
   v
approved development data
```

The generator writes candidates only.

It never writes directly into canonical train, validation or final holdout files.

### EvalSpec

Generation requirements are data, not code.

Example:

```yaml
name: scheduling-capability-boundary

languages:
  - es
  - en

families:
  - capability_meeting
  - capability_availability
  - scheduling_request
  - scheduling_availability

examples_per_family: 10
hard_negatives: true
```

The spec describes desired semantic coverage. It does not describe execution architecture.

## Dataset validation

All datasets pass through one canonical validator.

Checks:

```text
valid JSONL
required fields
valid language
valid route
valid intent/route mapping
unique id
non-empty message
family present
no exact duplicates
no forbidden split leakage
```

Where useful, also report normalized duplicates using:

```text
casefold
trim
whitespace normalization
```

Semantic similarity may be reported for review but must not automatically delete cases.

## Prompt evaluation

Prompts are versioned program inputs.

No prompt-management framework is required.

A stable identifier is enough:

```python
PORTFOLIO_PROMPT_ID = "portfolio-v3"
PORTFOLIO_PROMPT = """..."""
```

Every prompt evaluation report records:

```text
prompt_id
model
generation_config
dataset_hash
git_commit
metrics
```

This makes comparisons reproducible.

## Response grading

Use two grader types.

### Deterministic grader

Preferred whenever correctness can be computed.

Examples:

```text
JSON parseability
language
maximum length
forbidden text
runtime side effect
known factual inclusion
```

### Semantic grader

Used only when the property is inherently semantic.

Examples:

```text
relevance
groundedness
completeness
```

Input:

```text
question
evidence
response
criteria
```

Output must be structured:

```json
{
  "relevance": 0.96,
  "groundedness": 1.0,
  "completeness": 0.88,
  "reason": "..."
}
```

The reason is diagnostic. Metrics drive comparison.

A grader never receives capability execution authority.

## Scoring

Avoid one opaque score for the whole server.

Report dimensions separately.

Example:

```text
response cases          80
groundedness            99.4%
relevance               97.1%
language                100%
identity                100%
hallucination rate      0.0%
action safety           100%
```

An optional aggregate response-quality metric may exist for prompt comparison, but safety is never hidden inside it.

## Candidate comparison

Comparison is explicit:

```text
baseline report
      |
      v
candidate report
      |
      v
compare
```

Reports show deltas:

```text
                       baseline   candidate   delta

groundedness            97.5%      99.1%     +1.6
relevance                94.8%      96.3%     +1.5
hallucination             1.2%       0.0%     -1.2
p95                      890ms      905ms      +15
```

No generic auto-selection engine is required.

Promotion follows explicit gates.

## Promotion gates

Routing:

```text
route_accuracy            >= 95%
route_macro_f1            >= 95%
oos_recall                >= 95%
route_selective_risk      <= 2%
critical_false_scheduling == 0
routing p95               <= 100 ms
```

Safety:

```text
unexpected Calendar writes  == 0
unapproved bookings           == 0
unsupported capability calls == 0
```

Response-quality thresholds are introduced only after a measured baseline exists.

Do not invent arbitrary thresholds without evidence.

## Failure policy

An evaluation failure is data.

It is not automatically a request to change code.

```text
failure
   |
   v
classify cause
   |
   +-- implementation bug
   +-- dataset bug
   +-- representation gap
   +-- model limitation
   +-- ambiguous requirement
   +-- acceptable abstention
```

Never patch one benchmark sentence.

Bad:

```python
if "podés agendar" in text:
    return PORTFOLIO
```

Good:

```text
improve capability-vs-action representation
```

Changes must address a semantic family or structural problem.

## Package design

Keep evaluation code outside production packages whenever possible.

```text
server/
├── app/
│   └── ...
│
└── tests/
    └── evals/
        ├── intent_dataset.py
        ├── intent_metrics.py
        ├── run_intent_eval.py
        │
        ├── datasets/
        │   ├── generate.py
        │   ├── validate.py
        │   └── specs/
        │
        ├── responses/
        │   ├── cases.jsonl
        │   ├── evaluate.py
        │   └── grader.py
        │
        └── intents/
            ├── train.jsonl
            ├── train_oos.jsonl
            ├── validation.jsonl
            ├── challenge.jsonl
            ├── blind_test.jsonl
            └── final_holdout_v2.jsonl
```

Avoid deeper package trees unless a file becomes genuinely difficult to understand.

## Functions and interfaces

Prefer concrete functions:

```python
load_cases(path) -> list[Case]
validate_cases(cases) -> list[ValidationError]
generate_cases(spec, llm) -> list[Case]
evaluate_cases(cases, server) -> Report
grade_response(case, response) -> Grade
```

Do not define an interface around a component with one implementation.

Add a protocol only when two real implementations require the same boundary.

## Commands

There should be one obvious command for each operation.

```bash
make eval-dataset-generate
make eval-dataset-validate

make eval-routing
make eval-responses
make eval-safety
make eval-live

make eval-routes-v5
make eval-routes-final
```

Make targets compose scripts.

Scripts contain domain-specific execution only and reuse canonical parsing, validation and metrics.

## Reproducibility

Every report should include:

```text
git_commit
dataset
dataset_hash
candidate_id
model
seed
generation_config
timestamp
metrics
```

Use deterministic model settings where repeatability is required.

For stochastic behavior, repeat critical cases and report pass@k.

## Observability

Evaluation may consume tracing.

Tracing must never change behavior.

Useful spans include:

```text
router
portfolio_search
context_assembler
qwen_generation
stream_guard
scheduler
calendar
grader
```

Evaluation reports remain the source of acceptance decisions.

Tracing is diagnostic evidence only.

## DRY rules

There is one canonical implementation for:

```text
dataset parsing
dataset validation
metric calculation
report serialization
hash calculation
route mapping
```

Individual evaluation scripts contain only domain-specific execution.

Do not duplicate shared rules between scripts.

## KISS rules

Prefer:

```text
JSONL
plain dataclasses
plain functions
small scripts
Make targets
explicit loops
explicit errors
```

Avoid:

```text
framework callbacks
dependency injection containers
registries
reflection
dynamic plugins
metaprogramming
configuration-driven execution graphs
```

If a developer cannot follow an evaluation from Make target to result by reading a few files, the design is too complicated.

## Go-inspired design rules

### Clear is better than clever

Control flow must be visible.

### Errors are explicit

Malformed datasets fail with useful context.

Do not silently repair evaluation input.

### Small interfaces

Do not create abstractions before there are multiple real consumers.

### Accept data, return data

Prefer transformations such as:

```text
cases -> records -> metrics -> report
```

### Composition over inheritance

No evaluator class hierarchy.

### Dependencies point inward

Evaluation code may call the server.

Production server code never imports evaluation code.

### Boring code wins

An explicit loop is preferred over a generic framework that hides execution.

## End state

The development loop is:

```text
requirement
    |
    v
dataset/spec
    |
    +--> optional synthetic augmentation
    |
    v
candidate
    |
    v
unit tests
    |
    v
development eval
    |
    v
challenge
    |
    v
freeze
    |
    v
final holdout
    |
    v
E2E safety
    |
    +-- FAIL --> reject
    |
    +-- PASS --> promote
```

The evaluation system exists to make regressions visible and decisions evidence-based.

Its job is measurement, not orchestration.
