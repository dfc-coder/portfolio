# Evaluation system

Evaluation is development infrastructure. Production code does not depend on `tests/evals`.

The workflow is intentionally simple:

```text
spec -> dataset -> candidate -> execution -> metrics -> decision
```

There is no eval registry, plugin system, DAG, experiment database or prompt-management framework.

## Commands

```bash
make eval-dataset-validate
make eval-dataset-generate
make eval-responses
make eval-portfolio-prompts
make eval-safety
make eval-routing
make eval-scheduling
make eval-routes-v5
make eval-routes-final
```

`eval-dataset-generate` writes only to `tests/evals/generated/`. Generated cases are candidates for review and never mutate canonical train, validation, challenge or holdout files.

## Routing datasets

`tests/evals/intents/` is split by purpose:

- `train.jsonl`: supported-route training examples.
- `train_oos.jsonl`: explicit out-of-scope training examples for the four-class nonlinear candidate.
- `validation.jsonl`: calibration/development data.
- `challenge.jsonl`: historical 70-case development regression set.
- `blind_test.jsonl`: consumed historical blind set; it is regression evidence now, not an unseen final gate.
- `final_holdout_v2.jsonl`: frozen final acceptance set for the current candidate. Do not train, calibrate or generate from it.

The nonlinear route target is:

```text
PORTFOLIO
SCHEDULING
CONVERSATION
OOS
```

At runtime `OOS` means abstention: no business capability is invoked.

Leaf intent values remain diagnostic data. The runtime decision target is the business route.

## Synthetic generation

`datasets/specs/routing.json` owns labels and semantic-family descriptions. The LLM generates visitor messages only; it does not invent labels.

Generation runs one family/language batch at a time, rejects exact normalized duplicates against canonical datasets, and writes a review candidate under `tests/evals/generated/`.

`datasets/validate.py` is the canonical structural/leakage validator. It checks JSONL structure through the shared intent parser, split leakage, final-holdout isolation and optional generated candidates.

## Response evaluation

`responses/cases.jsonl` contains prompt-response contracts for `CONVERSATION` and `PORTFOLIO`.

`run_response_eval.py` executes the real `Responder` with current Qwen generation settings and current portfolio retrieval. It applies two graders:

1. deterministic checks for required content, forbidden claims and response length;
2. a structured semantic grader for relevance, groundedness, completeness, language, identity and action safety.

Semantic quality dimensions are reported independently. Until a stable baseline exists, only deterministic, language, identity and action-safety properties are strict gates.

Prompt IDs are versioned in `app/agent/context.py` and recorded in response-eval records so prompt changes can be compared reproducibly without a prompt framework.

### Portfolio prompt progression

The portfolio response prompt is intentionally implemented as four concrete versions:

```text
portfolio-v1  previous baseline
portfolio-v2  task-first / clear-direct
portfolio-v3  v2 semantics + XML boundaries for dynamic data
portfolio-v4  v3 + three synthetic few-shot behavior examples
```

`portfolio-v4` is the production default.

`make eval-portfolio-prompts` evaluates only portfolio response cases for all four versions in that exact order. Unchanged conversation cases are excluded from the ladder so they do not dilute prompt-version metrics.

The ladder writes:

```text
tests/evals/reports/portfolio-prompts/
  portfolio-v1.json
  portfolio-v2.json
  portfolio-v3.json
  portfolio-v4.json
  summary.json
```

The summary compares `v1 -> v2`, `v2 -> v3`, `v3 -> v4`, and `v1 -> v4`. Earlier versions remain measurable baselines; the strict ladder gate applies only to the final `portfolio-v4` hard contracts.

A single version can be run through the full response evaluator with:

```bash
make eval-responses PORTFOLIO_PROMPT_VERSION=v2
```

Few-shot examples are synthetic behavior demonstrations. They must not be copied from the frozen final holdout or from a consumed blind set.

## Reproducibility

New evaluation reports include dataset hash, git commit, candidate ID, model, timestamp and relevant generation settings.

A failed evaluation is evidence, not an instruction to patch a benchmark sentence. Fix semantic families, representation gaps, implementation bugs or requirements; do not add lexical rules for individual cases.
