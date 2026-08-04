---
id: ADR-002
title: Provider Abstraction
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-002 — Provider Abstraction

## Context

The project should not depend on a single LLM implementation.

## Decision

The engine communicates through a provider interface rather than directly with a specific API.

## Alternatives

* Direct LM Studio integration
* OpenAI SDK
* Provider abstraction

## Rationale

A provider abstraction allows new model backends to be added without changing business logic.

## Consequences

### Positive

* Easy provider replacement.
* Better testing.
* Reduced vendor lock-in.

### Negative

* Slightly more abstraction.
