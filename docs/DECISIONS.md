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
