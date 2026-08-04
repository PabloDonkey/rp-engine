---
id: ADR-005
title: Async-First Design
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-005 — Async-First Design

## Context

The application handles network requests and external providers.

## Decision

The project uses asynchronous APIs by default.

## Rationale

Asynchronous execution improves scalability and resource utilization.

## Consequences

### Positive

* Better concurrency.
* Efficient I/O.

### Negative

* Increased implementation complexity.
