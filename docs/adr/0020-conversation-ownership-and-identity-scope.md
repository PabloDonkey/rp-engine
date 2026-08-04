---
id: ADR-020
title: Conversation Ownership and Identity Scope
status: accepted
created: 2026-07-12
supersedes: [ADR-015]
superseded_by: [ADR-023]
---

# ADR-020 — Conversation Ownership and Identity Scope

## Context

Previous iterations mixed transport identity (Telegram user/chat IDs) with roleplay ownership and
conversation state boundaries.

That created model drift between documentation and runtime behavior and made adapter expansion riskier.

## Decision

Adopt session ownership as the canonical identity scope:

* A `Conversation` belongs to a `Session`.
* A `Session` is owned by one domain owner context:
        * `user` owner
        * `group` owner
* Adapters map external identities into domain identities before session lookup/creation.

Core/domain/application layers reason about `User`, `Group`, `Session`, and `Conversation`.

Core/domain/application layers do not reason about Telegram-specific identifiers.

## Rationale

* Keeps ownership and memory boundaries inside the domain model.
* Prevents adapter/platform identifiers from leaking into core business rules.
* Supports future adapters (Discord, web, CLI) without domain changes.
* Enables separate roleplay contexts for the same owner by session.

## Consequences

### Positive

* Private flows resolve to user-owned sessions.
* Group flows resolve to group-owned sessions.
* Session memory and conversation history are consistently session-scoped.
* Group and user isolation rules are explicit and testable.

### Negative

* Additional identity mapping and persistence components are required.
* Existing session-store indices and tests must support owner-scoped keys.

## Supersedes

* ADR-015 (Group Authorization Uses Conversation Identity) is superseded where it tied
        conversation storage identity directly to transport private/group identity.
