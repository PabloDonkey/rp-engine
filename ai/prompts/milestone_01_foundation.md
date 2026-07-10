# Milestone 1 Implementation Prompt

You are implementing Milestone 1 of RP Engine.

Read and respect these documents first:

* README.md
* docs/VISION.md
* docs/SPEC.md
* docs/ARCHITECTURE.md
* docs/DECISIONS.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

---

## Objective

Implement the first working vertical slice:

```
Telegram User
      |
      v
Telegram Adapter
      |
      v
Application Service
      |
      v
RP Engine Orchestrator
      |
      v
LLM Provider Interface
      |
      v
LM Studio
      |
      v
Telegram Response
```

---

## Requirements

Implement:

### Application startup

Create:

```
src/rp_engine/app/main.py
```

Responsibilities:

* Create FastAPI application
* Initialize dependencies
* Provide application lifecycle management

---

### Configuration

Implement:

```
src/rp_engine/infrastructure/config/
```

Use Pydantic Settings.

Configuration must support:

* Telegram bot token
* LM Studio base URL
* Model name
* Application settings

Values must come from environment variables.

---

### LLM Provider

Implement:

```
src/rp_engine/infrastructure/llm/
```

Create an LM Studio client using the OpenAI-compatible API.

Requirements:

* Async HTTP client
* Clear interface boundary
* No LM Studio-specific code outside infrastructure

---

### Core Service

Implement:

```
src/rp_engine/core/services/chat_service.py
```

Responsibilities:

* Receive a user message
* Create a conversation request
* Call the RP orchestrator
* Return generated response

No Telegram logic.

---

### RP Engine

Implement:

```
src/rp_engine/core/engine/orchestrator.py
```

Responsibilities:

* Coordinate prompt creation
* Call the LLM provider
* Return the generated response

Keep it simple.

Do not implement:

* Long-term memory
* Character system
* World simulation

Those are future milestones.

---

### Telegram Adapter

Implement:

```
src/rp_engine/adapters/telegram/
```

Responsibilities:

* Receive Telegram messages
* Pass messages to the application layer
* Send responses back

The adapter must not:

* Build prompts
* Call LM Studio directly
* Manage memory

---

## Testing

Add tests for:

* Chat service behavior
* Orchestrator behavior
* LM provider mocking
* Telegram adapter flow

External services should be mocked.

---

## Constraints

Do not:

* Change the project architecture
* Add unnecessary dependencies
* Introduce frameworks like LangChain
* Add databases
* Add vector stores
* Move files outside the current architecture

---

## Completion Criteria

The milestone is complete when:

1. The bot receives a Telegram message.
2. The message reaches the core service.
3. The core calls LM Studio.
4. The response returns to Telegram.
5. Tests pass.
6. Ruff and mypy pass.

Before coding:

* Explain the implementation plan.
* List files that will be created or modified.
* Wait for confirmation if architecture changes are needed.
