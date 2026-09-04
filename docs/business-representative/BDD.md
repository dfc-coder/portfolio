# BDD — Business Representative

## Goal

A portfolio visitor interacts with a concise server-side representative that answers grounded portfolio questions and safely coordinates meetings through explicit business capabilities.

## Feature: domain routing

### Scenario: route a portfolio question
Given the semantic router is ready
When the visitor asks about Diego's experience, projects, technologies or services
Then the router returns `PORTFOLIO`
And it does not choose a Python function or tool name

### Scenario: route ordinary conversation
Given the semantic router is ready
When the visitor greets the representative or asks an unrelated conversational question
Then the router returns `CONVERSATION`

### Scenario: route scheduling
Given the semantic router is ready
When the visitor wants to arrange or continue a meeting
Then the router returns `SCHEDULING`

## Feature: portfolio capability

### Scenario: answer a question supported by portfolio knowledge
Given the portfolio contains evidence about AWS
When the visitor asks about AWS experience
Then the representative invokes `PortfolioSearch`
And matching facts are passed to the responder
And the responder answers using those facts

### Scenario: portfolio knowledge does not support the claim
Given no matching portfolio fact survives the evidence threshold
When the visitor asks for that unsupported fact
Then `PortfolioSearch` returns no facts
And the responder does not invent the answer

### Scenario: follow-up retrieval excludes assistant text
Given a previous portfolio question and response exist
When the visitor asks a short follow-up
Then recent visitor turns may be used to resolve the query
And previous assistant text is not treated as retrieval evidence

## Feature: mixed-initiative scheduling

### Scenario: start with a date
Given there is no active scheduling task
When the visitor requests a meeting on a usable date
Then the scheduler extracts the date
And checks Calendar availability through the scheduling boundary
And stores offered slots as S1, S2, and so on

### Scenario: start without a date
Given no scheduling date is known
When the visitor asks to arrange a meeting
Then scheduling becomes active
And the scheduler asks for a day or date range

### Scenario: portfolio interruption preserves meeting data
Given an active scheduling task contains dates or slots
When the visitor asks a portfolio question
Then the representative invokes `PortfolioSearch`
And the responder answers from concrete facts
And scheduling memory remains unchanged
And a later scheduling turn can resume the meeting

### Scenario: unrecognized scheduling turn stays bounded
Given routing selects `SCHEDULING`
When the narrow scheduling interpreter cannot classify the message as a valid scheduling turn
Then the scheduler returns a clarification
And no other capability is silently invoked
And scheduling memory is not corrupted
And no Calendar write occurs

## Feature: safe booking

### Scenario: prepare without writing Calendar
Given an offered slot was selected
And visitor name, valid email and subject are known
When the scheduler has enough information
Then a pending booking is prepared
And no Calendar event is created
And an explicit approval action is shown in the interface

### Scenario: chat confirmation cannot authorize a write
Given a pending booking exists
When the visitor writes "sí, confirmo" or another free-form agreement
Then no Calendar write occurs from that text alone
And the pending booking remains available for explicit UI approval

### Scenario: explicit UI approval creates one event
Given a valid pending booking exists
When the visitor approves that booking through the explicit interface action
Then the approval boundary validates the pending booking and selected slot
And exactly one Calendar write is attempted
And success is reported only after Calendar accepts the write
And repeated approval is idempotent

### Scenario: Calendar write fails
Given a valid pending booking exists
When explicit UI approval is submitted
And Calendar returns an error
Then success is not reported
And the pending booking remains available according to approval policy

## Feature: streaming safety

### Scenario: grounded portfolio response streams normally
Given `PortfolioSearch` returned concrete evidence
When the responder generates the answer
Then the response is streamed while the model generates it
And owner-specific claims use only the supplied evidence

### Scenario: unverified completion claim is blocked
When free-form generation claims that a meeting already became booked or an invitation was sent without verified runtime state
Then the stream guard blocks that operational claim before it crosses SSE

## Feature: architecture remains simple

### Scenario: no tool framework exists
When the server code is inspected
Then business capabilities expose explicit methods and concrete result types
And there is no ToolRegistry, ToolExecutor, BaseTool, planner, ReAct loop or generic ToolResult

### Scenario: future tool adapter does not change the core
Given native function calling or MCP is introduced later
When a tool adapter invokes portfolio search
Then it delegates to `PortfolioSearch.search`
And the portfolio capability itself remains unchanged
