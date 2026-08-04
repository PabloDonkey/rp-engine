---
id: ADR-013
title: Separate Conversation Storage and Memory Strategy
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: [ADR-026]
---

# ADR-013 — Separate Conversation Storage and Memory Strategy

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
