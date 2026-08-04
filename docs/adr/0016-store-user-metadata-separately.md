---
id: ADR-016
title: Store User Metadata Separately From Message Content
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-016 — Store User Metadata Separately From Message Content

## Context

Group conversations require multi-user attribution for prompt construction.

Injecting names directly into stored text couples storage format to prompt rendering style and makes future formatting changes brittle.

## Decision

Conversation messages store speaker metadata in separate fields from text content.

Stored user messages may include:

* `user_id`
* `username`
* `display_name`
* `content`

Prompt rendering decides how to represent speaker attribution at generation time.

## Rationale

Separating identity data from content preserves clean memory records and allows multiple rendering strategies without rewriting history.

## Consequences

### Positive

* Message content remains clean and reusable.
* Prompt formatting can evolve independently.
* Better support for group and private prompt styles.

### Negative

* Storage and model types include additional optional fields.
