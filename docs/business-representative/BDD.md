# BDD — Business Representative

## Goal

A portfolio visitor interacts with a concise digital business representative powered by a server-side Qwen3.5-0.8B model. Deterministic workflow state and verification keep scheduling reliable without downloading model weights in the browser.

## Feature: business conversation

### Scenario: answer a portfolio question
Given the visitor opens the portfolio
And the server-side model is ready
When the visitor asks about experience, projects or services
Then the representative answers in the visitor's language
And owner-specific claims come only from the configured business profile
And no calendar operation is executed
And the browser does not download model weights

### Scenario: unknown owner-specific fact
Given a visitor asks for a rate, client, credential or fact absent from the business profile
When the representative answers
Then it must say that the information is not available
And it must not invent the fact

## Feature: state-first scheduling

### Scenario: enter scheduling workflow
Given the conversation stage is BUSINESS
When the visitor asks to schedule a meeting
Then scheduling intent enters the scheduling FSM
And the structured planner may request dates or availability

### Scenario: follow-up does not need repeated intent keywords
Given the representative previously offered slots S1, S2 and S3
And the conversation stage is SCHEDULING_SLOT
When the visitor says "el segundo"
Then the planner resolves S2 from structured session state
And it does not require the visitor to repeat "meeting", "agenda" or "availability"

### Scenario: stale or invented slot
Given the representative previously offered a set of slots
When a plan selects a slot not in that set
Then deterministic verification rejects the plan
And at most one repair attempt is allowed
And no booking side effect occurs

## Feature: bounded reflective ReAct

### Scenario: valid plan
Given the planner returns a schema-valid action allowed by the current state
When the verifier accepts the plan
Then the executor runs exactly that action
And the FSM transitions from the resulting observation

### Scenario: invalid plan is repaired once
Given the planner returns an invalid or semantically impossible action
When deterministic verification rejects it
Then the planner receives the validation issues
And it may repair the plan at most once by default
And a second invalid plan becomes a safe fallback

## Feature: safe booking

### Scenario: prepare a meeting
Given a valid offered slot exists
And the visitor supplied name, email and subject
When the executor prepares the booking
Then the backend stores a pending booking in the session
And no Google Calendar event is created
And the representative asks for explicit confirmation

### Scenario: ambiguous agreement is not confirmation
Given a pending booking exists
When the visitor says "Tuesday could work"
Then no calendar write occurs
And the booking remains pending

### Scenario: explicit confirmation creates the event
Given a pending booking exists
When the visitor explicitly says "Sí, confirmo" or "Book it"
Then FastAPI creates exactly one calendar event
And the representative only says the meeting is booked after the Calendar API succeeds
And the event invitation is sent to the visitor email

### Scenario: Calendar write fails
Given a pending booking exists
When the visitor explicitly confirms
And Google Calendar returns an error
Then the representative states that the operation did not complete
And it must not claim success
And the pending booking remains available for an explicit retry

## Feature: inference ownership

### Scenario: model stays server-side
Given the portfolio is served from Netlify
When a visitor opens the page
Then only the Vue application is downloaded
And prompts are sent by HTTPS to FastAPI
And Qwen3.5-0.8B remains resident in the infrastructure process running llama.cpp

### Scenario: one-slot inference
Given llama-server starts with one parallel slot
When multiple visitors send requests
Then FastAPI serializes LLM requests through one inference semaphore
And llama-server keeps one active slot
And prompt caching remains enabled
