---
id: ADR-003
title: Platform Independence
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-003 — Platform Independence

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
