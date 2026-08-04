---
id: ADR-012
title: Application Composition Root
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-012 — Application Composition Root

## Context

RP Engine uses adapters, application services, core business logic, and infrastructure implementations that must remain loosely coupled.

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
