# BDD — Business Representative

## Goal

A portfolio visitor interacts with a concise server-side representative that can answer grounded business questions and safely coordinate meetings.

## Feature: business conversation

### Scenario: answer a portfolio question with real streaming
Given the server-side model is ready
When the visitor asks about Diego's experience, projects, technologies or services
Then the turn is routed to business/general knowledge
And the answer is streamed while the model generates it
And owner-specific claims use only the configured business profile
And no Calendar side effect is executed

### Scenario: describe real agent tools
Given the scheduler can check availability and create a confirmed meeting
When the visitor asks "¿Podés usar herramientas?"
Then the representative describes those enabled capabilities
And it does not claim that it is unable to use tools
And it does not claim that an action already happened

### Scenario: unknown owner-specific fact
Given the requested fact is absent from the business profile
When the representative answers
Then it abstains rather than inventing the fact

## Feature: mixed-initiative scheduling

### Scenario: start with a date
Given there is no active scheduling task
When the visitor requests a meeting on a usable date
Then the scheduler extracts the date
And searches Calendar availability
And stores offered slots as S1, S2, and so on

### Scenario: start without a date
Given no scheduling date is known
When the visitor asks to arrange a meeting
Then scheduling becomes active
And the representative asks for a day or date range

### Scenario: select a slot from context
Given scheduling memory contains offered slots S1, S2 and S3
When the visitor says "el segundo"
Then S2 may be selected
And an unoffered slot cannot be selected
And the visitor does not need to repeat scheduling keywords

### Scenario: interruption preserves meeting data
Given an active scheduling task contains dates or slots
When the visitor asks a business question
Then the business answer uses real streaming
And scheduling memory remains unchanged
And a later scheduling turn can resume the meeting

### Scenario: false scheduling route escapes safely
Given routing initially selects scheduling
When the narrow scheduling interpreter concludes the message is not a scheduling turn
Then the representative reroutes only between business and general
And scheduling memory is preserved
And no Calendar operation executes

## Feature: safe booking

### Scenario: prepare without writing Calendar
Given an offered slot was selected
And visitor name, valid email and subject are known
When the scheduler has enough information
Then a pending booking is prepared
And no Calendar event is created
And explicit confirmation is requested

### Scenario: ambiguous agreement is not confirmation
Given a pending booking exists
When the visitor says "Tuesday could work"
Then no Calendar write occurs
And the pending booking remains available

### Scenario: explicit confirmation creates one event
Given a valid pending booking exists
When the visitor explicitly confirms using a phrase accepted by confirmation policy
Then exactly one Calendar write is attempted
And success is reported only after Calendar accepts the write
And the active scheduling task is cleared after success

### Scenario: Calendar write fails
Given a valid pending booking exists
When explicit confirmation is accepted
And Calendar returns an error
Then the representative reports failure
And does not claim that the meeting was created
And the pending booking remains available for retry

## Feature: streaming safety

### Scenario: capability statement is allowed
When the model says it can schedule a meeting after explicit confirmation
Then the stream guard allows the statement

### Scenario: unverified completion claim is blocked
When free-form generation claims that a meeting already became booked or an invitation was sent
Then the stream guard blocks that claim before it crosses SSE

## Feature: inference ownership

### Scenario: models stay server-side
Given the portfolio frontend is loaded
When the visitor uses the representative
Then only the web application is downloaded
And Qwen3.5-0.8B and Qwen3-Reranker-0.6B remain server-side
