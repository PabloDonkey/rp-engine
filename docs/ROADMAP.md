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

Stop replaying the whole conversation into every prompt. Give the engine a budget, and layers
that decide what fills it.

Designed in ADR-026 and settled in S021. See `docs/MEMORY.md` for what each layer does.

### Deliverables

Five layers behind one port, built in this order. Each ships on its own and is judged on its own.

| Story | Layer | What lands |
|---|---|---|
| S022 | 00 recent window | `TokenCounter`, the budget read from the model, `MemoryPipeline`, and a windowed history that replaces `DumpEverythingStrategy` |
| S023 | 01 rolling summary | the background worker, and the running "story so far" |
| S024 | 02 lorebook | authored facts with trigger keys, matched by Postgres full-text search, plus admin editing |
| S025 | 03 fact and state store | extracted facts with validity windows, and deterministic conflict resolution |
| S026 | 04 semantic recall | embeddings. Only if a concrete failure demands it. |

Alongside them: `MemorySettings` on the session, a `/memory` command, and admin panel controls.

### Success Criteria

* A long session never overflows the context window.
* A layer can be switched off per session without touching any other layer.
* Adding a sixth layer changes one line in the composition root and nothing else.
* What the budget dropped is visible in the generation trace, not silent.

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
