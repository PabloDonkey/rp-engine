---
id: ADR-009
title: Configuration Outside Code
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-009 — Configuration Outside Code

## Context

Runtime behavior should not require code modifications.

## Decision

Configuration is externalized through configuration files and environment variables.

## Rationale

Separating configuration from implementation simplifies deployment and testing.

## Consequences

### Positive

* Flexible deployments.
* Cleaner code.

### Negative

* Additional configuration management.
