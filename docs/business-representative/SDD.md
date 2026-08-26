# SDD — Portfolio Knowledge Agent

## Goal

Run a useful server-side portfolio assistant on a small local Qwen model with real streaming and grounded professional answers while keeping the runtime easy to reason about.

## Runtime

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     +-- BusinessRepresentative
     |      |
     |      +-- Responder
     |              |
     |              +-- ProfileRetriever --> Qwen3-Embedding-0.6B
     |              |                     cached document vectors
     |              +-- Qwen real stream
     |              +-- StreamGuard
     |
     +-- SessionStore
```

## Knowledge boundary

There is no semantic intent router for `BUSINESS`.

`business-profile.json` is flattened into retrievable natural-language documents. Their embeddings are computed once at startup. Every visitor turn uses the latest message as a single retrieval query.

```text
latest message
    |
    v
query embedding
    |
    v
cosine against cached profile documents
    |
    +-- score >= threshold --> BUSINESS + retrieved knowledge
    |
    +-- no qualifying document --> GENERAL
```

This makes the data source itself define the portfolio domain. Adding a skill, project or experience changes the retrievable knowledge without requiring a second list of routing examples.

The global boundary is `KNOWLEDGE_RELEVANCE_THRESHOLD`; PocketTrace records the top score and selected documents.

## Prompt boundary

`ContextAssembler` owns one base prompt. Portfolio owner facts are added only when retrieval produced qualifying documents.

The model receives:

```text
base instructions
+ verified runtime facts
+ optional retrieved portfolio knowledge
+ short visible conversation history
```

## Observability

PocketTrace is optional and fail-open. Useful spans are:

```text
profile_retrieval
context_assembler
qwen_generation
stream_guard
```

`profile_retrieval` includes the query, threshold, top score and selected document IDs/content.

## Package boundaries

```text
app/api             HTTP + SSE
app/agent           representative, knowledge, context, responder, guard
app/domain          session/profile/routing data
app/ports           LLM, embeddings, sessions
app/infrastructure  llama.cpp, embeddings, PocketTrace, config, sessions
app/bootstrap.py    dependency composition
```
