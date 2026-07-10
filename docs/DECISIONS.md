# Architecture Decisions

This document records significant architectural decisions made during the development of RP Engine.

Each decision captures the context, alternatives considered, rationale, and consequences.

The goal is to preserve the reasoning behind important choices, not simply record what changed.

---

# ADR-001 — Local-First Architecture

**Status:** Accepted

## Context

Users should be able to operate the engine without relying on cloud services.

## Decision

The engine is designed to operate entirely on local hardware whenever possible.

Cloud-hosted services are optional.

## Rationale

* User ownership of data
* Privacy
* Offline operation
* Lower operating cost

## Consequences

### Positive

* Conversations remain private.
* No recurring API costs.
* Works without Internet access.

### Negative

* Local hardware requirements.
* Performance depends on the user's machine.

---

# ADR-002 — Provider Abstraction

**Status:** Accepted

## Context

The project should not depend on a single LLM implementation.

## Decision

The engine communicates through a provider interface rather than directly with a specific API.

## Alternatives

* Direct LM Studio integration
* OpenAI SDK
* Provider abstraction

## Rationale

A provider abstraction allows new model backends to be added without changing business logic.

## Consequences

### Positive

* Easy provider replacement.
* Better testing.
* Reduced vendor lock-in.

### Negative

* Slightly more abstraction.

---

# ADR-003 — Platform Independence

**Status:** Accepted

## Context

The engine should support multiple communication platforms.

## Decision

Telegram, REST, CLI, and future interfaces are implemented as adapters.

## Rationale

The roleplay engine is the product.

Communication platforms are simply ways to interact with it.

## Consequences

### Positive

* Easier expansion.
* Better separation of concerns.

### Negative

* Slightly more project structure.

---

# ADR-004 — Layered Architecture

**Status:** Accepted

## Context

Business rules should remain isolated from external frameworks.

## Decision

The project adopts a layered architecture inspired by Ports & Adapters.

## Rationale

This keeps business logic independent from FastAPI, Telegram, and infrastructure concerns.

## Consequences

### Positive

* Easier testing.
* Cleaner dependencies.
* Better maintainability.

### Negative

* More interfaces.

---

# ADR-005 — Async-First Design

**Status:** Accepted

## Context

The application handles network requests and external providers.

## Decision

The project uses asynchronous APIs by default.

## Rationale

Asynchronous execution improves scalability and resource utilization.

## Consequences

### Positive

* Better concurrency.
* Efficient I/O.

### Negative

* Increased implementation complexity.

---

# ADR-006 — Modern Python Tooling

**Status:** Accepted

## Context

The project requires consistent development tooling.

## Decision

The standard development tools are:

* uv
* Ruff
* mypy
* pytest

## Rationale

These tools provide a fast, modern, and consistent development experience.

## Consequences

### Positive

* Fast dependency management.
* Consistent formatting.
* Static analysis.
* Automated testing.

### Negative

* Contributors must learn the toolchain.

---

# ADR-007 — Specification-Driven Development

**Status:** Accepted

## Context

Implementation should follow documented requirements rather than ad hoc feature development.

## Decision

Functional requirements are documented before implementation.

Architecture evolves from the specification.

## Rationale

A specification-first workflow improves clarity, planning, and maintainability.

## Consequences

### Positive

* Clear project direction.
* Easier reviews.
* Better traceability.
* Improved documentation.

### Negative

* Higher upfront documentation effort.

---

# ADR-008 — Strong Typing

**Status:** Accepted

## Context

The project is expected to grow in size and complexity.

## Decision

The codebase uses static typing throughout.

Type checking is enforced with mypy.

## Rationale

Strong typing improves maintainability, refactoring, and tooling support.

## Consequences

### Positive

* Earlier error detection.
* Better IDE support.
* Safer refactoring.

### Negative

* Additional type annotations.

---

# ADR-009 — Configuration Outside Code

**Status:** Accepted

## Context

Runtime behavior should not require code modifications.

## Decision

Configuration is externalized through configuration files and environment variables.

## Rationale

Separating configuration from implementation simplifies deployment and testing.

## Consequences

### Positive

* Flexible deployments.
* Cleaner code.

### Negative

* Additional configuration management.

---

# ADR-010 — Use LM Studio Python SDK

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

RP Engine requires a language model provider integration.

The first implementation target is LM Studio because it provides local model hosting and an OpenAI-compatible ecosystem for running local LLMs.

The project must avoid coupling the core engine to a specific LLM provider.

The integration approach must balance:

* simplicity
* maintainability
* future provider replacement
* access to LM Studio features

---

## Decision

Use the official LM Studio Python SDK as the initial LM Studio integration.

The SDK implementation will live exclusively in the infrastructure layer.

The core engine will communicate through an abstract LLM provider interface.

Architecture:

```text
core
 |
 | depends on abstraction
 v

LLMProvider interface

        ^
        |
        |

infrastructure

        |
        v

LM Studio Python SDK
```

The RP Engine core must never import or depend on the `lmstudio` package.

---

## Alternatives Considered

### Option 1 — Direct OpenAI-compatible HTTP API

Use LM Studio's OpenAI-compatible REST endpoint through an HTTP client.

Example:

```text
core
 |
LLM interface
 |
LM Studio HTTP client
 |
LM Studio API
```

### Advantages

* Uses a common API format.
* Easy provider replacement.
* Similar to OpenAI-compatible services.

### Disadvantages

* Requires maintaining HTTP integration code.
* Does not expose LM Studio-specific capabilities directly.

---

### Option 2 — Direct LM Studio SDK Usage Everywhere

Use the SDK throughout the application.

### Advantages

* Simple initial implementation.
* Full access to LM Studio features.

### Disadvantages

* Creates provider coupling.
* Makes future provider changes difficult.
* Violates architecture boundaries.

---

### Option 3 — LM Studio SDK Behind Provider Abstraction

Selected approach.

### Advantages

* Simple implementation.
* Keeps core independent.
* Allows future providers.
* Provides access to LM Studio features.

### Disadvantages

* Requires maintaining an abstraction layer.
* Some provider-specific features may need additional interfaces.

---

## Rationale

The RP Engine is designed as a reusable roleplay engine, not an LM Studio application.

The language model backend is an implementation detail.

Keeping LM Studio inside infrastructure provides:

* local-first operation
* clean architecture boundaries
* easier testing
* future provider flexibility

The SDK reduces unnecessary integration code while preserving architectural independence.

---

## Consequences

### Positive

* Less custom API handling.
* Better alignment with LM Studio capabilities.
* Cleaner infrastructure implementation.
* Core engine remains provider-agnostic.
* Easier mocking during tests.

---

### Negative

* The SDK becomes an infrastructure dependency.
* Switching providers still requires a new provider implementation.
* LM Studio-specific features require careful abstraction decisions.

---

## Implementation Rules

The following rules apply:

1. `lmstudio` imports are only allowed inside:

```text
src/rp_engine/infrastructure/llm/
```

2. Core modules must only depend on an interface.

3. Tests should mock the provider interface, not the SDK.

4. Provider-specific features must not leak into domain models.

---

## Future Review

This decision should be revisited if:

* LM Studio SDK becomes unsuitable.
* Another provider becomes the primary target.
* Multi-provider support requires a different abstraction.

If replaced, create a new ADR that supersedes this decision rather than modifying this document.


---

# ADR-011 — Application Composition Root

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

RP Engine uses adapters, core orchestration, and infrastructure implementations that must remain loosely coupled.

Dependency creation and runtime lifecycle ownership must be consistent across adapters, especially for Telegram polling startup and shutdown.

If adapters create services or infrastructure directly, architectural boundaries erode and testing becomes harder.

## Decision

The application layer is the composition root.

The application layer owns:

* configuration resolution
* dependency creation
* dependency wiring
* runtime lifecycle start/stop

Adapters only translate transport input/output and delegate to application services.

For Telegram specifically:

* application lifespan starts and stops Telegram runtime
* Telegram adapter does not construct services
* Telegram adapter does not initialize infrastructure

## Alternatives Considered

### Option 1 — Adapter-owned wiring

Allow each adapter to create its own service graph.

### Advantages

* Less initial setup in the app layer.

### Disadvantages

* Boundary violations.
* Duplicate wiring logic.
* Harder lifecycle coordination.
* Reduced testability.

---

### Option 2 — Distributed composition by module

Split dependency wiring across adapters and infrastructure modules.

### Advantages

* Smaller local setup functions.

### Disadvantages

* Hidden dependency graph.
* Ambiguous ownership of startup/shutdown.
* Higher maintenance overhead.

---

### Option 3 — Application-owned composition root

Selected approach.

### Advantages

* Clear ownership.
* Explicit dependency graph.
* Clean adapter boundaries.
* Easier integration testing.

### Disadvantages

* Slightly more up-front wiring code in the app layer.

## Rationale

RP Engine is intended to stay framework-agnostic in core business logic while supporting multiple adapters and providers.

A single composition root in the application layer enforces consistent boundaries and keeps lifecycle orchestration centralized.

This aligns with the project's dependency direction and keeps adapters thin.

## Consequences

### Positive

* Better architecture clarity.
* Predictable startup/shutdown behavior.
* Reduced coupling in adapters.
* Easier end-to-end internal flow tests.

### Negative

* Application wiring module grows as integrations increase.
* Requires discipline to avoid backsliding into adapter-owned setup.

## Implementation Rules

1. Build dependencies in the application layer.
2. Pass concrete implementations to core abstractions through constructors.
3. Keep adapters free from dependency graph construction.
4. Start and stop external runtimes from the application lifespan.


---

# ADR-012 — Separate Conversation Storage and Memory Strategy

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

Milestone 2 introduces persistent conversation memory.

Without explicit boundaries, the implementation can collapse storage, context selection, summarization, and retrieval into one component. That would make future evolution toward sliding windows, summaries, and retrieval strategies harder.

RP Engine needs interchangeable storage implementations and interchangeable context-building strategies.

## Decision

Treat memory as two independent concerns:

1. Conversation Storage
2. Memory Strategy

Conversation storage is responsible only for persistence operations such as:

* `save_message()`
* `load_messages()`
* `clear()`

Memory strategy is responsible only for converting stored conversation history into model context.

Dependency direction:

```text
core

        ports/
                conversation_store.py
                memory_strategy.py


infrastructure/

        storage/
                json_conversation_store.py
```

For Milestone 2, implement:

* `JsonConversationStore`
* `DumpEverythingStrategy`

`DumpEverythingStrategy` returns all available stored messages as context.

Do not implement summarization, retrieval, embeddings, or hybrid memory logic in this milestone.

## Alternatives Considered

### Option 1 — Single memory manager owning all concerns

One component stores messages, chooses context, summarizes, and retrieves.

### Advantages

* Faster initial implementation.
* Fewer files and interfaces.

### Disadvantages

* Tight coupling across unrelated responsibilities.
* Harder to replace storage without touching context logic.
* Harder to introduce new strategies incrementally.

---

### Option 2 — Separate storage and strategy concerns

Selected approach.

### Advantages

* Clear responsibilities.
* Independent replaceability of persistence and context logic.
* Better testability per concern.
* Safer path for future advanced memory strategies.

### Disadvantages

* Slightly more abstraction in Milestone 2.

## Rationale

RP Engine is designed for incremental evolution.

Separating storage from strategy keeps Milestone 2 simple while preserving compatibility with future context policies.

This avoids premature coupling and keeps architectural options open for later milestones.

## Consequences

### Positive

* Core owns stable contracts for both concerns.
* Infrastructure can add new store backends independently.
* Memory strategies can evolve without changing persistence code.
* Prompt assembly receives explicit context output from strategy logic.

### Negative

* More interfaces to maintain.
* Additional wiring in the composition root.

## Implementation Rules

1. Do not create a generic memory manager that combines storage and strategy.
2. Keep persistence decisions out of memory strategy implementations.
3. Keep context selection decisions out of storage implementations.
4. Route chat flow through store load, strategy build, prompt build, LLM call, then store save.
5. Milestone 2 strategy must be `DumpEverythingStrategy` only.


---

# Future Decisions

Future ADRs should follow this template.

```markdown
# ADR-XXX — Title

**Status:** Proposed | Accepted | Superseded | Rejected

## Context

What problem is being solved?

## Decision

What was decided?

## Alternatives

What other options were considered?

## Rationale

Why was this option selected?

## Consequences

### Positive

...

### Negative

...
```

Each ADR should describe a single architectural decision.

If a decision changes in the future, create a new ADR that supersedes the previous one rather than rewriting history.
