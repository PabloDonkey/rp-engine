---
id: ADR-006
title: Modern Python Tooling
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-006 — Modern Python Tooling

## Context

The project requires consistent development tooling.

## Decision

The standard development tools are:

* uv
* Ruff
* mypy
* pytest

## Rationale

These tools provide a fast, modern, and consistent development experience.

## Consequences

### Positive

* Fast dependency management.
* Consistent formatting.
* Static analysis.
* Automated testing.

### Negative

* Contributors must learn the toolchain.
