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
