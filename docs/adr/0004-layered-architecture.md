---
id: ADR-004
title: Layered Architecture
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-004 — Layered Architecture

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
