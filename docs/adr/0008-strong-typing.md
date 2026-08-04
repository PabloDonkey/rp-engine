---
id: ADR-008
title: Strong Typing
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-008 — Strong Typing

## Context

The project is expected to grow in size and complexity.

## Decision

The codebase uses static typing throughout.

Type checking is enforced with mypy.

## Rationale

Strong typing improves maintainability, refactoring, and tooling support.

## Consequences

### Positive

* Earlier error detection.
* Better IDE support.
* Safer refactoring.

### Negative

* Additional type annotations.
