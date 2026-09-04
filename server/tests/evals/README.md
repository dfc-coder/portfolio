# Evaluation system

Evaluation is development infrastructure. Production code does not depend on `tests/evals`.

The workflow is intentionally simple:

```text
spec -> dataset -> execution -> metrics -> decision
```

There is no eval registry, plugin system, DAG, experiment database or prompt-management framework.

## Commands

```bash
make eval-dataset-validate
make eval-dataset-generate
make eval-responses
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

`responses/cases.jsonl` contains response contracts for `CONVERSATION` and `PORTFOLIO`.

`run_response_eval.py` executes the same current `Responder` and current portfolio retrieval used by the agent. It applies two graders:

1. deterministic checks for required content, forbidden claims and response length;
2. a structured semantic grader for relevance, groundedness, completeness, language, identity and action safety.

Semantic quality dimensions are reported independently. Deterministic, language, identity and action-safety properties remain strict gates.

Prompt IDs from `app/agent/prompts.py` are recorded for traceability. The evaluator does not select historical prompt versions and production does not contain prompt experiment switches.

## Reproducibility

New evaluation reports include dataset hash, git commit, candidate ID, model, timestamp and relevant generation settings.

A failed evaluation is evidence about the current agent. Fix semantic families, representation gaps, implementation bugs or requirements; do not patch individual benchmark sentences.
