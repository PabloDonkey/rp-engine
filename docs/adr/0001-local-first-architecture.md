---
id: ADR-001
title: Local-First Architecture
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-001 — Local-First Architecture

## Context

Users should be able to operate the engine without relying on cloud services.

## Decision

The engine is designed to operate entirely on local hardware whenever possible.

Cloud-hosted services are optional.

## Rationale

* User ownership of data
* Privacy
* Offline operation
* Lower operating cost

## Consequences

### Positive

* Conversations remain private.
* No recurring API costs.
* Works without Internet access.

### Negative

* Local hardware requirements.
* Performance depends on the user's machine.
