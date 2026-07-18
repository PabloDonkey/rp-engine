# Architecture Refactor — Deprecate Character State (ADR + Documentation Audit)

Before making any code changes, perform a complete architecture audit to determine whether the current "Character State" concept is actually used by the engine.

The goal is to simplify the architecture by following the current implementation and aligning with the design philosophy used by systems such as SillyTavern: Character Card + Memory + Lore.

Do not assume Character State is necessary simply because it exists in the documentation.

---

# Phase 1 — Architecture Audit

Search the entire repository, including:

Documentation:
- ARCHITECTURE.md
- DOMAIN_MODEL.md
- DECISIONS.md
- ROADMAP.md
- SPEC.md
- VISION.md
- README.md
- DATABASE_MODEL.md
- ADRs

Source code:
- domain
- application
- infrastructure
- adapters
- prompt builder
- memory manager
- repositories
- services
- orchestrator
- tests

Search for:

- CharacterState
- Character State
- character_state
- runtime state
- relationship state
- emotional state
- inventory
- persistent variables

Determine:

1. Is Character State actively used by the engine?
2. Is it referenced by prompt generation?
3. Is it modified during conversations?
4. Is it consumed by application services?
5. Is it only persisted but never used?
6. Which files would be affected if Character State were removed?

Produce a concise audit report before making changes.

---

# Phase 2 — Architecture Decision Record

Create a new ADR documenting this architectural decision.

Suggested title:

ADR-XXX — Defer Character State

Document:

## Context

Originally, the architecture introduced Character State as a structured runtime model intended to hold evolving information such as:

- relationship
- emotions
- inventory
- objectives
- variables

However, an implementation audit showed that Character State is currently not used by the engine.

The engine derives narrative continuity from:

- Character Definition (Character Card)
- Character Memories
- Conversation History

No current feature depends on a structured Character State.

## Decision

Defer Character State.

The primary domain model becomes:

Session
    ├── Conversation
    ├── Character
    ├── Character Memory
    └── Lore

Character Definition remains the reusable template.

Character evolution is represented through memories rather than a structured Character State.

Structured runtime state may be introduced in the future only if a concrete feature requires deterministic state (for example inventory, health, quests, simulation mechanics, etc.).

## Consequences

Positive:

- simpler domain model
- fewer persistence concepts
- fewer repositories
- simpler PostgreSQL schema
- aligns implementation with actual behavior
- follows proven conversational architecture

Negative:

- structured runtime simulation is deferred
- future gameplay mechanics may introduce a focused runtime model

---

# Phase 3 — Documentation Update

Update all documentation consistently.

Replace references to Character State where appropriate.

The resulting architecture should describe:

Character
    ├── Character Card
    └── Character Memories

Session
    ├── Conversation
    ├── Characters
    └── Memories

World
    └── Lore

Do not simply delete text.

Rewrite sections so the documentation remains coherent.

Update diagrams where necessary.

---

# Phase 4 — Code Audit

Do NOT immediately delete Character State code.

Instead:

Identify every implementation that currently exists:

- domain objects
- repository interfaces
- JSON persistence
- PostgreSQL models
- migrations
- dependency injection
- tests

Classify each item as:

- actively used
- persistence only
- unused
- obsolete after ADR

Produce a migration plan showing what can safely be removed now and what should remain temporarily for backward compatibility.

---

# Constraints

Do not remove functionality that is currently used.

Prefer deprecating unused concepts over deleting them immediately.

Keep backward compatibility whenever practical.

The objective is to align the architecture with the current engine, not with speculative future features.

The final result should leave the project centered on four primary concepts:

- Character Definition (Character Card)
- Character Memory
- Conversation
- Lore

Future structured runtime state should only be introduced when justified by implemented features.