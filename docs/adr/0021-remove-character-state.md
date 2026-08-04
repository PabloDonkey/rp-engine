---
id: ADR-021
title: Remove Character State as a Domain Concept
status: accepted
created: 2026-07-17
supersedes: []
superseded_by: []
---

# ADR-021 — Remove Character State as a Domain Concept

## Context

Initial architecture language described a dedicated structured Character State model for
relationship, emotion, inventory, and other runtime variables.

An implementation audit showed the current engine runtime does not consume a structured
Character State entity in generation or conversation workflows.

Current continuity is produced from:

* Character Definition (character card)
* Conversation Memory
* World Lore

The historical compatibility artifact (`state.json` written during JSON character creation)
was removed after confirming no runtime dependency.

## Decision

Remove Character State as an active domain concept.

The primary active runtime model is:

* Session
* Conversation
* Character Definition
* Memory
* Lore

Character evolution is represented through memory and conversation history.

Structured runtime state may be introduced in the future only when a concrete deterministic
feature requires it (for example inventory mechanics, health systems, quest flags, or
simulation variables), under a new ADR with focused scope.

## Rationale

* Align architecture with actual implementation behavior.
* Reduce conceptual and documentation drift.
* Keep persistence model simpler during current milestones.
* Follow a memory-first conversational architecture.

## Consequences

### Positive

* Simpler domain model and documentation.
* Clearer boundaries between character definition and session memory.
* Fewer speculative persistence concepts.
* Lower migration risk while PostgreSQL adoption is incremental.

### Negative

* Structured gameplay-style mechanics are out of current scope.
* Future deterministic features require a focused model-introduction ADR.

## Implementation Notes

* Removed legacy JSON `state.json` write path from character creation.
* Updated tests to assert character card persistence only.
* PostgreSQL schema remains unchanged because no Character State table exists.
