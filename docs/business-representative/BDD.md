# BDD — Business Representative

## Goal

A portfolio visitor interacts with a concise server-side business representative. Semantic interpretation handles natural language, scheduling state is stored as facts, capabilities declare what can execute, and deterministic safety gates protect side effects.

## Feature: business conversation

### Scenario: answer a portfolio question with real streaming
Given the visitor opens the portfolio
And the server-side model is ready
When the visitor asks about experience, projects, technologies, tools, or services
Then the representative routes the turn to business/general knowledge
And the answer is streamed as the model generates it
And owner-specific claims are grounded in the configured business profile
And no calendar operation is executed

### Scenario: unknown owner-specific fact
Given a visitor asks for a fact absent from the business profile
When the representative answers
Then it must abstain rather than invent the fact

## Feature: mixed-initiative scheduling

### Scenario: start scheduling with a date
Given there is no active scheduling workflow
When the visitor asks for a meeting on a usable date
Then the semantic interpreter extracts a scheduling request and date
And scheduling belief stores the date range
And `calendar.search_availability` becomes eligible
And available slots are stored as S1, S2, and so on

### Scenario: scheduling starts without a date
Given there is no known scheduling date range
When the visitor asks to arrange a meeting
Then the scheduling workflow becomes active
And `scheduling.ask_dates` becomes eligible
And the representative asks for a day or date range

### Scenario: select a slot from context
Given scheduling belief contains offered slots S1, S2 and S3
When the visitor says "el segundo"
Then the semantic interpreter returns act `select` with slot S2
And only an offered slot may be selected
And the visitor does not need to repeat scheduling keywords

### Scenario: business interruption preserves scheduling belief
Given an active scheduling workflow contains offered slots
When the visitor asks "¿Tenés herramientas?"
Then the turn is handled as a business question
And the answer uses the grounded real-stream path
And the existing scheduling dates and slots remain unchanged

### Scenario: false scheduling route escapes safely
Given the semantic router initially routes a message to scheduling
When the scheduling interpreter determines the message is `not_applicable`
Then the system reroutes only across business/general candidates
And the scheduling belief is preserved
And no scheduling capability executes

## Feature: declarative capability resolution

### Scenario: impossible capabilities are filtered before selection
Given a visitor intent has been interpreted
And the current belief state is known
When the capability registry resolves candidates
Then capabilities missing required facts are excluded
And capabilities forbidden by current facts are excluded
And the model cannot select an excluded capability

### Scenario: one eligible capability needs no semantic selector
Given exactly one capability is applicable
When the bounded loop resolves the next action
Then that capability executes directly
And no reranker or Qwen capability judge is required

### Scenario: several eligible capabilities use semantic selection
Given several safe capabilities are applicable
When a capability must be selected
Then the reranker ranks only those eligible capabilities
And Qwen is used only if the ranking remains ambiguous

## Feature: bounded capability loop

### Scenario: multi-step scheduling turn
Given selecting a slot also supplies all required visitor details
When `scheduling.select_slot` succeeds
Then its observation may request one additional step
And the loop recomputes belief facts
And `scheduling.prepare_booking` may become eligible
And execution never exceeds `AGENT_MAX_STEPS`

### Scenario: failed validation is bounded
Given a selected capability violates a deterministic invariant
When the safety gate rejects it
Then no side effect occurs
And the loop may reconsider at most `AGENT_MAX_REPAIRS` times
And it never enters an unrestricted reflection loop

## Feature: safe booking

### Scenario: prepare a meeting without writing Calendar
Given an offered slot was selected
And visitor name, email, and subject are known
When `scheduling.prepare_booking` executes
Then a pending booking is stored
And no Google Calendar event is created
And the representative requests explicit confirmation

### Scenario: ambiguous agreement is not explicit confirmation
Given a pending booking exists
When the visitor says "Tuesday could work"
Then `calendar.create_booking` is not eligible
And no calendar write occurs
And the pending booking remains available

### Scenario: explicit confirmation creates exactly one event
Given a pending booking exists
And its selected slot was previously offered
When the visitor explicitly says "Sí, confirmo" or another phrase accepted by the confirmation policy
Then `calendar.create_booking` becomes eligible
And the safety gate validates the write
And FastAPI creates exactly one Calendar event
And success is reported only after the Calendar API succeeds

### Scenario: Calendar write fails
Given a valid pending booking exists
When explicit confirmation is accepted
And Google Calendar returns an error
Then the representative reports that the operation did not complete
And it must not claim success

## Feature: inference ownership

### Scenario: models stay server-side
Given the portfolio frontend is loaded
When the visitor uses the representative
Then only the web application is downloaded
And Qwen3.5-0.8B and Qwen3-Reranker-0.6B remain resident server-side

### Scenario: future classifier is additive
Given reviewed routing examples become available
When a supervised multi-head classifier is introduced
Then high-confidence domain/relation/act decisions may bypass the reranker
And low-confidence cases still fall through to the reranker
And unresolved ambiguity may still fall through to the Qwen judge
