---
id: ADR-022
title: Adopt Character Card Specification v3
status: accepted
created: 2026-07-17
supersedes: []
superseded_by: [ADR-023]
---

# ADR-022 — Adopt Character Card Specification v3

## Context

RP Engine requires a portable character definition format for import, export, and ecosystem
compatibility.

Maintaining a custom character card schema would duplicate existing community standards,
increase maintenance burden, and reduce interoperability.

## Decision

Adopt Character Card Specification v3 as the external character definition contract.

Canonical source:

* `docs/SPEC_V3.md`

The Character Card represents portable character definition concerns such as:

* identity (name and descriptive metadata)
* personality
* scenario
* behavior-guiding fields
* initial greeting (`first_mes`)

Engine-specific information remains outside the card:

* `owner_id`
* `visibility`
* database identifiers
* memories
* sessions
* runtime metadata

RP Engine maps Character Card v3 into its internal `Character` domain model through
application/domain mapping and validation layers.

## Consequences

### Positive

* Better compatibility with existing character-card ecosystems.
* Simpler import/export interoperability.
* Less custom schema maintenance in RP Engine.

### Negative

* Internal model requires explicit mapping from external card fields.
* Future Character Card spec versions require compatibility and migration handling.
