# Intent routing datasets

These splits are intentionally separated so routing changes are measured without tuning against the final holdout.

- `train.jsonl`: supervised examples used to fit the linear classifier. Contains only known intents.
- `validation.jsonl`: used to calibrate confidence and margin thresholds. Contains known intents and explicit out-of-scope cases.
- `challenge.jsonl`: the 70 historical routing cases already used during semantic-router development. It is a regression/development set, not a generalization claim.
- `blind_test.jsonl`: frozen holdout used only after implementation, training data and thresholds are frozen. Do not use its failures to tune the same experiment.

An out-of-scope case is represented with both `intent` and `route` set to `null`. OOS is not trained as another business intent; it is an abstention target.

Normal development loop:

```bash
make check
make eval-intents-challenge
```

Final holdout gate, only after the experiment is frozen:

```bash
make eval-intents-blind
```

The blind command trains only from `train.jsonl`, calibrates only from `validation.jsonl`, then evaluates the frozen holdout with the Definition of Done gates.
