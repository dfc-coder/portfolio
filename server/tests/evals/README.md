# Intent / route evaluation data

The evaluation corpus is split by purpose, not by convenience:

- `train.jsonl`: supervised examples used to train the business-route classifier.
- `validation.jsonl`: calibrates confidence and margin thresholds; it includes OOS examples with `intent=null` and `route=null`.
- `challenge.jsonl`: the historical 70 routing cases already used during development. It is a development/challenge set, not a final generalization test.
- `blind_test.jsonl`: frozen holdout used only after the challenge gate is satisfied. Do not tune examples, thresholds, prototypes or classifier settings from blind-test results.

The runtime decision target is the business route only:

```text
PORTFOLIO
SCHEDULING
CONVERSATION
```

Leaf `intent` values remain in the dataset as diagnostics and for semantic-family organization, but they are not trained as runtime classes. This prevents distinctions such as `portfolio_query` versus `capability_query` from consuming classifier capacity when both invoke the same `PORTFOLIO` capability.

Semantic families must not cross train, validation and blind splits. The challenge set intentionally preserves its historical per-case families because it is already contaminated by prior routing work and is used only for regression/development comparison.

Training uses the existing Qwen routing embeddings plus an offline multinomial logistic regression. Threshold calibration maximizes validation coverage subject to route selective risk <= 2% and zero critical false scheduling. The exported artifact contains only the route classifier weights and calibrated thresholds; scikit-learn is not a runtime dependency.

The supervised router is not promoted into `bootstrap.py` until the frozen blind route gates pass.
