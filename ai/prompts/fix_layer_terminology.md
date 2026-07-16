# Copilot Implementation Prompt — Fix Layer Terminology & Align Architecture

Review the current project architecture and align the package naming with the documented architecture.

This task is primarily an architectural cleanup. The goal is to improve clarity without changing behavior.

## Current Situation

The documentation describes the dependency flow as:

```text
Adapter
    ↓
Application
    ↓
Core
    ↓
Infrastructure
```

However, the current package structure appears closer to:

```text
adapters
    ↓
core/services
    ↓
core/domain
    ↓
infrastructure
```

The name `core/services` is misleading because these services perform **application orchestration**, not domain logic.

---

# Objective

Move toward a clean layered architecture where responsibilities are explicit.

Target architecture:

```text
adapters
    ↓
application
    ↓
core
    ↓
infrastructure
```

Where:

```text
application/
    services/
        chat_service.py
        ...
```

contains orchestration and use cases.

And:

```text
core/
    domain/
    engine/
```

contains business logic and RP engine concepts.

---

# Responsibilities

## Adapters

Responsible for transport-specific concerns only.

Examples:

* Telegram
* Discord
* CLI
* REST
* Future adapters

Owns concepts such as:

* Telegram commands
* Username lookup
* Authorization
* Message splitting
* Beta registration
* Transport formatting

Adapters should never contain RP logic.

---

## Application Layer

Responsible for orchestrating use cases.

Examples:

* ChatService
* ContinueService
* RegenerateService
* Session orchestration
* Calling providers
* Persistence coordination
* Transaction boundaries

The application layer coordinates work but should contain little or no business rules.

---

## Core Layer

Contains RP engine business logic.

Examples include:

* Character
* World
* Conversation
* Memory
* Generation
* Prompt construction
* Story state
* Context building
* Domain models
* Domain services
* Business rules

The core should know nothing about Telegram or any other transport.

The core must never depend on adapters.

---

## Infrastructure

Responsible for implementations.

Examples:

* LM Studio provider
* Storage
* JSON persistence
* Database implementations
* Configuration
* Filesystem
* External APIs

Infrastructure implements interfaces defined by higher layers.

---

# Refactoring

Evaluate whether `core/services` should become:

```text
application/services/
```

If these services primarily:

* coordinate use cases,
* invoke multiple components,
* manage workflows,
* call repositories/providers,

then they belong in the Application layer.

Keep true domain logic inside the Core.

Refactor imports as necessary while preserving behavior.

---

# Documentation

Update all architecture documentation to reflect the final layering.

Review and update files such as:

* ARCHITECTURE.md
* DOMAIN_MODEL.md
* DECISIONS.md
* ROADMAP.md
* developer documentation
* package diagrams

Ensure all diagrams use consistent terminology.

Remove references that imply application services belong to the Core if that is no longer true.

---

# Validation

After refactoring:

* Run the full test suite.
* Ensure no circular dependencies have been introduced.
* Verify dependency direction remains:

```text
Adapters
    ↓
Application
    ↓
Core

Infrastructure
    ↑
implements interfaces owned by higher layers
```

The Core must not depend on:

* Telegram
* Discord
* HTTP
* FastAPI
* python-telegram-bot
* authorization
* transport-specific concepts

---

# Acceptance Criteria

* `core/services` has been evaluated and, if appropriate, moved to `application/services`.
* Package names accurately reflect responsibilities.
* Architecture documentation matches the implementation.
* Imports are updated with no behavioral changes.
* Dependency direction remains clean and one-way.
* The Core contains only RP engine concepts and business logic.
* Transport-specific concerns remain isolated in adapters.
* All tests continue to pass without regression.
