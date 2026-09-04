# Business Representative Prompt Design

## Goal

Build the production agent with one clear response contract. Prompt-engineering lessons are incorporated into the current prompt; they are not represented as runtime experiments.

Production code has one conversation prompt and one portfolio prompt.

## Canonical portfolio prompt

The current portfolio prompt combines the techniques that improved the agent behavior:

1. task-first opening;
2. explicit output rules;
3. XML boundaries around dynamic data;
4. three synthetic few-shot behavior examples.

The prompt lives in `server/app/agent/prompts.py`. `ContextAssembler` only injects runtime state, capabilities, policy and retrieved evidence.

## Design rules

### Task first

The first instruction states exactly what the agent must do: answer the visitor directly using supplied evidence for facts and declared capabilities for actions.

### Specific output contract

The portfolio prompt requires:

- the visitor's language;
- concise and useful answers;
- third-person references to the portfolio subject;
- first person only for declared agent capabilities;
- facts grounded only in supplied knowledge;
- explicit abstention when evidence is missing;
- no invented clients, rates, availability, results, credentials, dates, teams, documents, contact channels or external sources;
- no side-effect claims without verified runtime state;
- a normal response limit of 120 words.

These are observable response rules, not hidden reasoning steps.

### Structured dynamic data

Runtime data is delimited with descriptive XML tags:

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

Dynamic XML text is escaped before interpolation. XML improves boundaries for the model; it is not an authorization or prompt-injection security boundary.

### Few-shot behavior examples

The canonical prompt includes three synthetic examples covering:

1. answering a supported factual question directly;
2. abstaining when evidence is missing;
3. describing a declared capability without claiming that an external action already happened.

The examples are fictional behavior demonstrations and are not evidence about the real portfolio subject.

## Runtime structure

```text
prompts.py
  -> current instructions

ContextAssembler
  -> portfolio subject
  -> capabilities
  -> owner policy
  -> runtime state
  -> retrieved knowledge

Responder
  -> LLM
  -> StreamGuard
  -> visitor
```

The runtime does not select between historical prompt versions. There is no prompt registry, prompt manager, prompt ladder or experiment switch in production.

## Validation

Tests and evals validate the current agent behavior. They do not define the product architecture.

`make eval-responses` runs the current `Responder` and current portfolio retrieval against response contracts. Safety remains separate from semantic quality scores.

Hard contracts include:

```text
non-empty output
forbidden content
length contract
language contract
identity contract
action-safety contract
```

Semantic quality includes:

```text
relevance
groundedness
completeness
```

A semantic score cannot compensate for a hard-contract failure.

## Go-inspired constraints

Keep the implementation concrete:

- one current prompt per response mode;
- plain constants;
- one `ContextAssembler`;
- explicit XML rendering functions;
- no prompt registry;
- no prompt manager;
- no templating framework;
- no inheritance hierarchy;
- no dynamic plugin loading.

The production path should be understandable by reading `app/agent/prompts.py`, `app/agent/context.py`, and `app/agent/responder.py` in that order.
