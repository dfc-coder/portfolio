# SDD — Portfolio Business Representative

## Goal

Run a useful server-side representative on a small local Qwen model with explicit business capabilities, real streaming, grounded portfolio answers and Calendar writes protected by human approval.

The design intentionally avoids a tool framework, generic capability registry, ToolExecutor, planner, ReAct loop, agent graph, cross-encoder reranker and LLM routing judge.

## Runtime

```text
Vue / Netlify
     |
     | HTTPS + SSE
     v
FastAPI
     |
     v
BusinessRepresentative
     |
     +-- CONVERSATION ----------------------> Responder
     |
     +-- PORTFOLIO ---> PortfolioSearch ----> Responder
     |                    |
     |                    +--> profile knowledge + embeddings
     |
     +-- SCHEDULING ---> Scheduler
                            |
                            +--> SlotService ---> Calendar

Explicit UI approval
     |
     v
BookingApproval ---> Calendar ---> GoogleCalendarGateway
```

`BookingApproval` is deliberately outside free-form chat. It validates the pending booking and explicit user approval before the Calendar command crosses the side-effect boundary.

## BusinessRepresentative

`BusinessRepresentative` is the explicit orchestrator. It appends the visitor turn, asks the router for a domain, invokes one capability, streams or returns the result, and persists the assistant turn.

Its control flow is intentionally boring:

```text
SCHEDULING  -> Scheduler
PORTFOLIO   -> PortfolioSearch -> Responder
otherwise   -> Responder
```

It contains no generic tool dispatcher, planner or dynamic function registry.

## Semantic routing

`SemanticRouter` answers one question: what class of problem is the visitor trying to solve?

The only domains are:

```text
CONVERSATION
PORTFOLIO
SCHEDULING
```

Route descriptions are embedded once and cached. Each visitor turn requires one query embedding and local cosine similarity against the cached route vectors.

During an active scheduling workflow, route descriptions are contextualized so a portfolio or conversational interruption can preserve scheduling memory. The router still returns only the domain; workflow relation is derived by the scheduling consumer.

## PortfolioSearch

`PortfolioSearch` is the first explicit business capability:

```python
search(query: str) -> SearchResult
```

It returns concrete values:

```text
SearchResult
└── facts: tuple[Fact, ...]
    ├── text
    └── source
```

The capability hides its retrieval backend. Today it uses `business-profile.json`, cached embeddings and dense cosine retrieval. A future document store, vector database or reranker can replace that backend without changing `BusinessRepresentative` or `Responder`.

Only recent visitor turns are used to build a follow-up retrieval query. Previous assistant text is not fed back as search evidence.

## Responder

`Responder` does not retrieve portfolio knowledge. It receives concrete evidence from the orchestrator and renders a response from that evidence.

For a portfolio turn:

```text
PortfolioSearch
     |
     v
SearchResult.facts
     |
     v
Responder
```

If no supported fact survives the evidence threshold, `RELEVANT_KNOWLEDGE` is explicitly empty and the prompt requires abstention instead of invention.

`StreamGuard` remains a narrow safety layer for generated text, especially unverified side-effect claims. Correct control flow is the primary guarantee; the guard is not the authorization mechanism.

## Scheduling and Calendar

Scheduling state remains data rather than a conversational stage machine:

```text
SchedulingMemory
- requested date range
- offered slots
- selected slot id
- visitor name
- visitor email
- subject
- pending booking
```

The Calendar interface lives with the scheduling consumer. `SlotService` uses it for availability reads. `BookingApproval` uses it for the booking command after explicit UI approval.

`Scheduler` never receives Calendar directly and never performs Calendar writes. Free-form chat may prepare a `PendingBooking`, but only the explicit approval boundary may execute `create_booking`.

## Failure behavior

A routing decision is not a Python function dispatch. If a scheduling message cannot be interpreted as a valid scheduling turn, `Scheduler` returns a scheduling clarification and does not silently invoke another capability.

Calendar success is reported only after the command boundary receives a concrete booking result. Calendar errors do not produce a success claim and leave the pending booking available according to the approval policy.

## Observability

PocketTrace is optional and fail-open. Relevant spans include `router`, `portfolio_search`, `context_assembler`, `qwen_generation`, `stream_guard` and scheduling operations. Tracing observes decisions but does not participate in them.

## Package boundaries

```text
app/api                    HTTP + SSE + explicit approval endpoints
app/agent                  representative, router, scheduler, responder, guard
app/portfolio              PortfolioSearch + concrete result types
app/domain                 conversation/profile/routing/scheduling data
app/scheduling             Calendar boundary, policy, slots, approval
app/infrastructure/knowledge  profile retrieval backend
app/infrastructure         llama.cpp, embeddings, Calendar gateways, tracing, config, sessions
app/ports                  legacy/shared technical ports only
app/bootstrap.py           dependency composition
```

There is intentionally no `tools/` package yet. Native function calling or MCP can be added later as thin adapters over these capabilities without changing the core.
