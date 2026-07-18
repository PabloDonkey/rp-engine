# Roadmap

This document describes the planned evolution of RP Engine.

The roadmap is organized into milestones that incrementally deliver the capabilities defined in the functional specification.

Implementation details and individual development tasks are intentionally excluded.

---

# Guiding Principles

Development follows these priorities:

1. Build the foundation.
2. Deliver vertical slices.
3. Keep the system functional at every milestone.
4. Prefer incremental improvements over large rewrites.
5. Complete infrastructure before advanced features.

---

# Milestone 1 — Project Foundation

**Status:** Completed

## Goal

Establish the project's architecture, tooling, and development workflow.

### Deliverables

* Project structure
* Development environment
* Documentation
* CI-ready tooling
* Logging
* Configuration
* Dependency injection
* Testing framework
* Telegram adapter vertical slice
* LM Studio SDK integration
* Core LLM provider abstraction
* Unit and integration test coverage for Milestone 1 scope
* Ruff and mypy quality tooling

### Success Criteria

* Project builds successfully.
* Static analysis passes.
* Tests execute successfully.
* Documentation is established.
* Telegram adapter to core to provider flow is operational.

---

# Milestone 2 — Core Conversation Engine

## Goal

Support basic conversations through a provider.

### Deliverables

* Conversation lifecycle
* Session management
* Message persistence
* Prompt construction
* Provider abstraction
* LM Studio provider

### Success Criteria

A user can hold a complete conversation with the engine.

---

# Milestone 3 — Telegram Adapter

## Goal

Expose the engine through Telegram.

### Deliverables

* Telegram adapter
* Incoming messages
* Outgoing responses
* Session mapping
* Error handling

### Success Criteria

Users can interact with the engine entirely through Telegram.

---

# Milestone 4 — Memory

## Goal

Introduce persistent long-term memory.

### Deliverables

* Conversation summaries
* Memory retrieval
* Context management
* Memory persistence

### Success Criteria

The engine recalls relevant past information across long conversations.

---

# Milestone 5 — Character / World / Session Model

## Goal

Introduce reusable roleplay assets and session-owned roleplay context.

### Deliverables

* Character model
* World model
* Session model (`user_id` + `character_id` + `world_id`)
* Character selection use case
* Session-based conversation ownership

### Success Criteria

* One user can maintain multiple sessions.
* Sessions reference characters and worlds.
* Conversation persistence is session-scoped.

---

# Milestone 6 — Characters

## Goal

Strengthen persistent character continuity.

### Deliverables

* Character definitions
* Personality
* Character-memory continuity rules
* Prompt-level consistency improvements

### Success Criteria

Characters remain consistent across conversations.

---

# Milestone 7 — World State

## Goal

Maintain a persistent world.

### Deliverables

* World model
* Locations
* Objects
* Events
* Persistent changes

### Success Criteria

The world evolves consistently across sessions.

---

# Milestone 8 — Multiple Providers

## Goal

Support interchangeable language model providers.

### Deliverables

* Provider interface
* Additional providers
* Provider configuration

### Success Criteria

Changing providers requires configuration only.

---

# Milestone 9 — Additional Adapters

## Goal

Support additional communication platforms.

Possible adapters include:

* REST API
* CLI
* Discord
* Matrix

### Success Criteria

New adapters require no changes to the domain.

---

# Milestone 10 — Tool Ecosystem

## Goal

Expand engine capabilities through tools.

Possible tools include:

* Image generation
* Search
* Memory inspection
* Character editor
* World editor

### Success Criteria

Tools integrate without changing the core architecture.

---

# Milestone 11 — Production Readiness

## Goal

Prepare the project for long-term use.

### Deliverables

* Performance improvements
* Monitoring
* Backup
* Recovery
* Documentation
* Packaging

### Success Criteria

The project is stable, maintainable, and suitable for long-running deployments.

---

# Deferred Features

These features are intentionally postponed until the core engine is mature.

* Voice interaction
* Multi-agent conversations
* Visual interfaces
* Advanced planning systems
* Distributed execution

---

# Completion Policy

A milestone is considered complete when:

* Functional requirements are satisfied.
* Tests are implemented.
* Documentation is updated.
* Static analysis passes.
* Code review is complete.

---

# Living Document

This roadmap is expected to evolve.

New milestones may be added as the project grows, but changes should remain aligned with the project's vision and functional specification.
