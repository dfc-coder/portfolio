# BDD — Business Representative

## Goal

A portfolio visitor interacts with a concise digital business representative that can answer owner-specific business questions and coordinate a meeting without downloading or running the language model in the browser.

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
Then it must say that the information is not available or ask a clarifying business question
And it must not invent the fact

## Feature: agenda discovery

### Scenario: visitor asks for availability
Given Google Calendar is connected
When the visitor asks for a meeting in a date range
Then the representative calls the availability tool
And the tool reads Calendar free/busy data
And proposed slots are inside configured business hours
And proposed slots respect minimum notice, meeting duration and buffer
And only free/busy intervals are exposed to the agent

### Scenario: stale or invented slot
Given the representative previously offered a set of slots
When a booking is prepared for a slot not in that set
Then the booking preparation is rejected
And the representative must query availability again

## Feature: safe booking

### Scenario: prepare a meeting
Given a valid offered slot exists
And the visitor supplied name, email and subject
When the representative prepares the booking
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
Then the backend creates exactly one calendar event
And the representative only says the meeting is booked after the Calendar API succeeds
And the event invitation is sent to the visitor email

### Scenario: Calendar write fails
Given a pending booking exists
When the visitor explicitly confirms
And Google Calendar returns an error
Then the representative states that nothing was booked
And it must not claim success

## Feature: inference ownership

### Scenario: model stays server-side
Given the portfolio is served from Netlify
When a visitor opens the page
Then only the Vue application is downloaded
And prompts are sent by HTTPS to FastAPI
And tokens return over SSE
And Qwen3.5-2B remains resident in the infrastructure process running llama.cpp

### Scenario: one-slot inference
Given llama-server starts with one parallel slot
When multiple visitors send requests
Then FastAPI serializes LLM requests through one inference semaphore
And llama-server keeps one active slot
And prompt caching remains enabled for repeated system/business prefixes
