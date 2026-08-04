---
id: ADR-018
title: Internal User Identity
status: accepted
created: 2026-07-11
supersedes: []
superseded_by: []
---

# ADR-018 — Internal User Identity

## Context

External identifiers from adapters (for example Telegram user IDs) were being used directly to
identify users in engine-facing flows and conversation storage keys.

This coupling makes the core model transport-aware and complicates multi-adapter reuse.

## Decision

The engine uses internal collision-resistant UUIDs as primary user identifiers.

External platform identifiers are stored only as linked identities and resolved by adapters through
an identity resolution service before calling application use cases.

## Rationale

Internal IDs preserve domain ownership of identity and keep core logic independent from transport
platforms.

## Consequences

### Positive

* Core user model is provider-agnostic.
* Adapters can map identities without changing core business logic.
* Future transports can reuse the same user model.

### Negative

* Additional resolver and identity persistence components are required.
