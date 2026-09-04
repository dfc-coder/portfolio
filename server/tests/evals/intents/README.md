# Intent routing datasets

These files are evaluation/training data. Production routing does not import this package.

- `train.jsonl`: supported-route training examples.
- `train_oos.jsonl`: explicit out-of-scope examples for the current nonlinear routing candidate.
- `validation.jsonl`: development/calibration data.
- `challenge.jsonl`: historical 70-case development regression set.
- `blind_test.jsonl`: consumed historical blind set. Keep it only as regression evidence; it is no longer an unseen gate.
- `final_holdout_v2.jsonl`: frozen final acceptance set for the current nonlinear candidate. Do not train, calibrate or generate from it.

A dataset OOS case uses both `intent` and `route` as `null`. The nonlinear evaluator may represent that internally as an `oos` class, but OOS is not a production business route. At runtime it means abstention and no business capability invocation.

Normal development loop:

```bash
make eval-dataset-validate
make eval-routes-v5
```

Run the final holdout only after the candidate artifact and thresholds are frozen:

```bash
make eval-routes-final
```

After a final holdout has been used to guide changes, it is consumed and must not be presented again as unseen evidence for the next candidate.
