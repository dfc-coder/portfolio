# Business Representative Prompt Design

## Goal

Keep response prompts explicit, small and measurable while applying the prompt-engineering rules used by the Business Representative evaluation workflow.

This is not a prompt framework. The server has four concrete portfolio prompt versions and one production default.

```text
portfolio-v1  baseline from the previous HEAD
     |
     v
portfolio-v2  task-first / clear-direct
     |
     v
portfolio-v3  v2 semantics + XML boundaries for dynamic data
     |
     v
portfolio-v4  v3 + three few-shot behavior examples
```

`portfolio-v4` is the production default. Older versions remain executable only so the same evaluation corpus can measure each change directly.

## Design rules

### 1. Task first

A portfolio prompt starts with the action the model must perform, not only with a role description.

`portfolio-v2` adds a direct opening instruction while keeping the `portfolio-v1` data format unchanged.

### 2. Be specific about the output contract

The prompt explicitly requires:

- the visitor's language;
- concise, useful answers;
- third-person references to the portfolio subject;
- facts grounded only in supplied knowledge;
- explicit abstention when evidence is missing;
- no invented clients, rates, availability, results, credentials or dates;
- no side-effect claims without verified runtime state;
- a normal response limit of 120 words.

These are output guidelines, not hidden reasoning steps.

### 3. Delimit dynamic data

`portfolio-v3` keeps instructions as plain prompt text and wraps interpolated data in descriptive XML tags:

```text
<portfolio_subject>
<timezone>
<agent_capabilities>
<owner_policy>
<runtime_state>
<relevant_knowledge>
```

Knowledge facts are rendered as:

```xml
<fact source="projects.0">...</fact>
```

Dynamic XML text is escaped before interpolation. XML tags improve boundaries for the model; they are not an authorization or prompt-injection security boundary.

### 4. Show difficult behavior with few-shot examples

`portfolio-v4` adds three synthetic examples. They cover semantic families rather than benchmark sentences:

1. answer a supported factual question directly;
2. abstain when evidence is missing;
3. describe a declared capability without claiming that a side effect already happened.

The examples are explicitly marked fictional and are not evidence about the real portfolio subject.

Examples are structured with descriptive tags:

```text
<examples>
  <example>
    <sample_input>...</sample_input>
    <ideal_output>...</ideal_output>
    <why_it_is_good>...</why_it_is_good>
  </example>
</examples>
```

Do not copy final-holdout or consumed-blind messages into prompt examples.

## Evaluation

Prompt versions are measured on the same portfolio response cases, with the same model, generation configuration and graders.

Run the complete ladder with:

```bash
make eval-portfolio-prompts
```

The command writes:

```text
tests/evals/reports/portfolio-prompts/
  portfolio-v1.json
  portfolio-v2.json
  portfolio-v3.json
  portfolio-v4.json
  summary.json
```

The summary compares:

```text
v1 -> v2
v2 -> v3
v3 -> v4
v1 -> v4
```

Older prompt versions are baselines. Only the final `portfolio-v4` hard contracts are a strict failure gate for the ladder command.

A single version can also be evaluated through the normal response evaluator by setting `PORTFOLIO_PROMPT_VERSION`.

## Scoring policy

Hard contracts remain separate from semantic quality scores.

Hard contracts:

```text
non-empty output
forbidden content
length contract
language contract
identity contract
action-safety contract
```

Semantic quality:

```text
relevance
groundedness
completeness
```

A semantic average cannot compensate for a hard-contract failure.

## Go-inspired constraints

Keep the implementation concrete:

- four prompt constants;
- one explicit version-selection function;
- one default version;
- one ordered evaluation loop;
- JSON reports;
- no prompt registry;
- no prompt manager;
- no templating framework;
- no inheritance hierarchy;
- no dynamic plugin loading.

The version progression should be readable directly from `app/agent/context.py` and the evaluation sequence directly from `tests/evals/run_portfolio_prompt_ladder.py`.
