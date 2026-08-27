# BDD — Portfolio Knowledge Agent

## Goal

A portfolio visitor interacts with a concise server-side assistant that answers grounded questions about Diego Fernando Cano's professional experience, projects, skills and services.

## Feature: portfolio knowledge conversation

### Scenario: answer a portfolio question with real streaming
Given the server-side model and embedding service are ready
When the visitor asks about Diego's experience, projects, technologies or services
Then relevant business-profile facts are retrieved from cached embeddings
And the answer is streamed while the model generates it
And owner-specific claims use only the configured business profile

### Scenario: unknown owner-specific fact
Given the requested fact is absent from the supplied business context
When the assistant answers
Then it abstains rather than inventing the fact

### Scenario: general conversation
Given no portfolio document passes the relevance threshold
When the visitor sends a general message
Then the assistant responds without injecting portfolio facts

### Scenario: follow-up question
Given prior visible conversation turns exist
When the visitor asks a short follow-up
Then recent visible turns remain available as conversational context
And any owner-specific answer remains grounded in retrieved portfolio knowledge

## Feature: streaming safety

### Scenario: owner identity disclaimer is allowed
When the model states that it is not Diego
Then the stream guard allows the statement

### Scenario: owner impersonation is blocked
When free-form generation claims to be Diego
Then the stream guard blocks that claim before it crosses SSE

## Feature: inference ownership

### Scenario: models stay server-side
Given the portfolio frontend is loaded
When the visitor uses the assistant
Then only the web application is downloaded
And the conversational Qwen model and Qwen3-Embedding-0.6B remain server-side
