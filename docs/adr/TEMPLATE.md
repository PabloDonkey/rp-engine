# ADR template

Copy this file to `NNNN-kebab-title.md`, take the next free number, and fill it in.
Delete the parts that do not apply. See [README.md](README.md) for the front matter rules.

````markdown
---
id: ADR-XXX
title: Short Title in Title Case
status: proposed
created: YYYY-MM-DD
supersedes: []
superseded_by: []
---

# ADR-XXX — Short Title in Title Case

## Context

What problem is being solved?

## Decision

What was decided?

## Alternatives

What other options were considered?

## Rationale

Why was this option selected?

## Consequences

### Positive

...

### Negative

...

## Supersedes

Required when `supersedes` is not empty. Name each ADR and state **how much** of it this
decision replaces — the whole ADR, or named parts only.
````

Each ADR describes a single architectural decision.

When a decision changes, write a new ADR that supersedes the old one. Do not rewrite history in
the old file. The only edits an existing ADR may receive are its `superseded_by` line and, where
the change is small and additive, a dated `## Amendment` section.
