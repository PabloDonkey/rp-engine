# Architecture

## Purpose

This document describes the high-level architecture of RP Engine.

It defines the system's structure, component responsibilities, dependency rules, and interaction patterns. It complements the functional specification by explaining **how the system is organized**, without prescribing implementation details.

---

# Architectural Goals

The architecture is designed to achieve the following goals:

* Platform independence
* Provider independence
* Long-term maintainability
* Testability
* Modularity
* Extensibility
* Separation of concerns

---

# Architectural Style

RP Engine follows a layered architecture inspired by Hexagonal Architecture (Ports & Adapters).

The core domain is isolated from external technologies.

External systems communicate with the application through adapters.

```mermaid
flowchart TD

Telegram --> Adapter
REST --> Adapter
CLI --> Adapter

Adapter --> Application
Application --> Engine
Engine --> Domain

Engine --> Memory
Engine --> LLM

Memory --> Storage
LLM --> Provider
```

The core engine must not depend on Telegram, FastAPI, LM Studio, or any other external framework.

---

# Layers

## Adapters

Adapters translate external requests into application requests.

Examples include:

* Telegram
* REST API
* CLI
* Discord
* Matrix

Responsibilities:

* Receive external requests
* Validate transport-specific data
* Convert requests into application models
* Return responses to the caller

Adapters contain no business logic.

Adapter-specific responsibilities:

* Parse transport syntax (for example, Telegram slash commands)
* Enforce transport-level authorization and invocation policy
* Translate transport actions into application use cases
* Return transport-appropriate responses

Adapters must not implement prompt construction, memory strategy logic, or direct LLM interaction.

### Transport Commands

Transport commands belong to adapters.

Example for Telegram:

* `/help` is handled entirely by the Telegram adapter
* `/continue` is translated to `ChatService.continue_story(...)`
* `/clear` is translated to `ChatService.clear_conversation(...)`

The engine and application services never parse Telegram command syntax.

---

## Application

The application layer coordinates use cases.

Responsibilities:

* Conversation lifecycle
* Dependency orchestration
* Transaction boundaries
* Request validation
* Error handling

The application layer does not implement domain rules.

The application layer exposes explicit, transport-agnostic use cases.

Current use-case API:

* `ChatService.send_message(...)`
* `ChatService.continue_story(...)`
* `ChatService.clear_conversation(...)`

Adapters call these use cases directly.

FastAPI and Telegram are both adapters over the same application API.

The application layer is also the composition root.

Responsibilities of the composition root:

* Resolve configuration
* Create infrastructure implementations
* Wire abstractions to concrete implementations
* Expose application services to adapters
* Own startup and shutdown lifecycle

---

## Engine

The engine contains the orchestration logic for roleplay interactions.

Responsibilities include:

* Prompt construction
* Memory retrieval
* Character loading
* World loading
* Response generation workflow
* Context assembly

The engine coordinates services but avoids platform-specific concerns.

---

## Domain

The domain layer contains the business concepts.

Examples:

* Conversation
* Session
* Character
* World
* Memory
* Message

The domain should contain no framework dependencies.

---

## Infrastructure

Infrastructure provides implementations for external concerns.

Examples:

* File storage
* Databases
* Logging
* Configuration
* LLM providers

Infrastructure depends on the domain, never the reverse.

For language model integration, infrastructure implements the provider contract defined in:

```text
core/ports/llm_provider.py
```

---

# Dependency Rules

Dependencies flow inward.

```text
Adapters
    ↓
Application
    ↓
Engine
    ↓
Domain

Infrastructure ─────► Domain
Infrastructure ─────► Engine
Infrastructure ─────► Core Ports
```

Allowed dependencies:

* Adapters → Application
* Application → Engine
* Engine → Domain
* Infrastructure → Domain
* Infrastructure → Core Ports

Forbidden dependencies:

* Domain → FastAPI
* Domain → Telegram
* Domain → LM Studio
* Domain → File System
* Engine → Telegram
* Engine → FastAPI

---

# Telegram Lifecycle Ownership

Telegram runtime lifecycle is owned by the application layer.

Expected flow:

```text
Application lifespan
    ├─ start Telegram runtime
    └─ stop Telegram runtime

Telegram adapter
    └─ delegate message handling to ChatService
```

Rules:

* The Telegram adapter must not create `ChatService`.
* The Telegram adapter must not initialize infrastructure dependencies.
* The Telegram adapter must not own startup/shutdown orchestration.

This keeps adapter responsibilities focused on transport translation and preserves clean boundaries.

---

# Major Components

## Conversation Manager

Responsible for:

* Session lookup
* Message ordering
* Conversation lifecycle

---

## Memory Manager

Responsible for:

* Recent context
* Long-term memory
* Retrieval
* Summarization

---

## Prompt Builder

Responsible for assembling model input.

Possible inputs include:

* Recent messages
* Character information
* World information
* Memory retrieval
* System prompts

---

## Provider Interface

Defines a common abstraction for language model providers.

Example implementations:

* LM Studio
* Ollama
* llama.cpp
* OpenAI-compatible APIs

The engine communicates only through this abstraction.

---

# Request Flow

A typical conversation follows this sequence.

```mermaid
sequenceDiagram

participant User
participant Adapter
participant Application
participant Engine
participant Memory
participant Provider

User->>Adapter: Message

Adapter->>Application: Request

Application->>Engine: Generate Reply

Engine->>Memory: Load Context

Memory-->>Engine: Context

Engine->>Provider: Generate

Provider-->>Engine: Response

Engine->>Memory: Persist

Engine-->>Application: Reply

Application-->>Adapter: Response

Adapter-->>User: Message
```

Telegram command flow:

```text
/continue
    ↓
Telegram Adapter
    ↓
ChatService.continue_story(...)
    ↓
RP Engine
```

```text
/clear
    ↓
Telegram Adapter
    ↓
ChatService.clear_conversation(...)
```

```text
/help
    ↓
Telegram Adapter
    ↓
Telegram reply
```

Invocation policy for Telegram:

* Private chats: normal messages and supported commands are processed.
* Group chats: normal messages are ignored; only supported commands are processed.

Authorization flow:

* Adapter checks whitelist authorization before use-case invocation.
* Unauthorized users receive a configured transport message.
* Authorized users continue through normal adapter translation.

---

# State Management

The engine maintains several categories of state.

## Conversation State

* Recent messages
* Active participants
* Session metadata

---

## Character State

* Personality
* Knowledge
* Relationships
* Persistent attributes

---

## World State

* Locations
* Objects
* Events
* Global facts

---

## Memory State

* Long-term summaries
* Retrieved memories
* Embeddings (optional)

---

# Configuration

Configuration is external to the application.

Examples include:

* Active provider
* Model name
* Memory limits
* Feature flags
* Storage backend

The application should not require code changes to modify runtime behavior.

---

# Extensibility

The architecture is designed so new capabilities can be added by extension rather than modification.

Examples include:

* New adapters
* New LLM providers
* New storage backends
* Alternative memory implementations

Existing business logic should remain unchanged whenever possible.

---

# Design Principles

The architecture follows these principles:

* Separation of concerns
* Dependency inversion
* Composition over inheritance
* Explicit interfaces
* Immutable data where practical
* Async-first design
* Strong typing
* High cohesion
* Low coupling

---

# Architecture Decision Records

Major architectural decisions are documented separately in `DECISIONS.md`.

This document describes the architecture.

`DECISIONS.md` explains why specific architectural choices were made.
