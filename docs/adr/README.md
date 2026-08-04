# Architecture Decisions

This folder records significant architectural decisions made during the development of RP Engine.

Each decision captures the context, alternatives considered, rationale, and consequences.
The goal is to preserve the reasoning behind important choices, not simply record what changed.

One decision = one file. These were a single document (`docs/DECISIONS.md`) until 2026-08-03; see
[S028](../../.devloop/archive/S028-2026-08-03-split-decisions-into-adr-files.md) for the split.

## Index

`Replaced by` lists any ADR that replaced this one **in whole or in part**. Read the replacing
ADR's `## Supersedes` section for the exact scope — most supersessions here are partial.

| ADR | Title | Status | Created | Replaced by |
|---|---|---|---|---|
| [ADR-001](0001-local-first-architecture.md) | Local-First Architecture | accepted | 2026-07-10 | — |
| [ADR-002](0002-provider-abstraction.md) | Provider Abstraction | accepted | 2026-07-10 | — |
| [ADR-003](0003-platform-independence.md) | Platform Independence | accepted | 2026-07-10 | — |
| [ADR-004](0004-layered-architecture.md) | Layered Architecture | accepted | 2026-07-10 | — |
| [ADR-005](0005-async-first-design.md) | Async-First Design | accepted | 2026-07-10 | — |
| [ADR-006](0006-modern-python-tooling.md) | Modern Python Tooling | accepted | 2026-07-10 | — |
| [ADR-007](0007-specification-driven-development.md) | Specification-Driven Development | accepted | 2026-07-10 | — |
| [ADR-008](0008-strong-typing.md) | Strong Typing | accepted | 2026-07-10 | — |
| [ADR-009](0009-configuration-outside-code.md) | Configuration Outside Code | accepted | 2026-07-10 | — |
| [ADR-010](0010-lm-studio-python-sdk.md) | Use LM Studio Python SDK | accepted | 2026-07-10 | — |
| [ADR-011](0011-conversation-model-as-provider-boundary.md) | Conversation Model As Provider Boundary | accepted | 2026-07-12 | — |
| [ADR-012](0012-application-composition-root.md) | Application Composition Root | accepted | 2026-07-10 | — |
| [ADR-013](0013-separate-conversation-storage-and-memory-strategy.md) | Separate Conversation Storage and Memory Strategy | accepted | 2026-07-10 | ADR-026 (partial) |
| [ADR-014](0014-transport-commands-belong-to-adapters.md) | Transport Commands Belong to Adapters | accepted | 2026-07-10 | — |
| [ADR-015](0015-group-authorization-uses-conversation-identity.md) | Group Authorization Uses Conversation Identity | **superseded** | 2026-07-10 | ADR-020 |
| [ADR-016](0016-store-user-metadata-separately.md) | Store User Metadata Separately From Message Content | accepted | 2026-07-10 | — |
| [ADR-017](0017-transport-adapters-handle-message-size-limits.md) | Transport Adapters Handle Message Size Limits | accepted | 2026-07-11 | — |
| [ADR-018](0018-internal-user-identity.md) | Internal User Identity | accepted | 2026-07-11 | — |
| [ADR-019](0019-provider-owns-conversation-serialization.md) | Provider Owns Conversation Serialization | accepted | 2026-07-12 | — |
| [ADR-020](0020-conversation-ownership-and-identity-scope.md) | Conversation Ownership and Identity Scope | accepted | 2026-07-12 | ADR-023 (partial) |
| [ADR-021](0021-remove-character-state.md) | Remove Character State as a Domain Concept | accepted | 2026-07-17 | — |
| [ADR-022](0022-adopt-character-card-spec-v3.md) | Adopt Character Card Specification v3 | accepted | 2026-07-17 | ADR-023 (narrowed) |
| [ADR-023](0023-scenario-centric-architecture.md) | Scenario-Centric Architecture | accepted | 2026-07-22 | ADR-024 (partial) |
| [ADR-024](0024-postgres-as-sole-persistence-backend.md) | Postgres as Sole Persistence Backend | accepted | 2026-07-24 | — |
| [ADR-025](0025-session-reset-tiers.md) | Session Reset Tiers: `/restart` Preserves Player Settings, `/clear` Resets Them | accepted | 2026-07-27 | — |
| [ADR-026](0026-layered-memory.md) | Layered Memory: One Port, Five Sources, Per-Session Toggles | accepted | 2026-08-02 | — |

## File naming

`NNNN-kebab-title.md` — the number is zero-padded to four digits so plain alphabetical sorting
stays correct past ADR-99. The number never changes once assigned, and a number is never reused.

## Front matter

Every ADR file starts with this block. It is the single source of truth for status and links;
the body must not repeat them.

```yaml
---
id: ADR-024                 # matches the file name
title: Postgres as Sole Persistence Backend
status: accepted            # proposed | accepted | superseded | rejected
created: 2026-07-26         # the date the decision was made
supersedes: [ADR-023]       # ADRs this one replaces, whole or in part
superseded_by: []           # ADRs that replaced this one, whole or in part
---
```

Rules:

* `status: superseded` means the **whole** ADR is dead. An ADR that lost only some of its rules
  keeps `status: accepted` and records the replacement in `superseded_by`. Most entries here are
  of the second kind.
* `supersedes` and `superseded_by` must **mirror** each other. If ADR-024 supersedes ADR-023, then
  ADR-023 lists ADR-024 in `superseded_by`. The test below enforces this.
* An ADR with a non-empty `supersedes` must also carry a `## Supersedes` prose section that states
  the scope. A list of ids does not tell a reader which parts died.

## Adding an ADR

1. Copy [TEMPLATE.md](TEMPLATE.md) to `NNNN-kebab-title.md` with the next free number.
2. Fill in the front matter and the body.
3. If it replaces an earlier decision, fill `supersedes`, write the `## Supersedes` section, and
   add the back link to the older file's `superseded_by`.
4. Add a row to the index table above.
5. Run `uv run pytest tests/unit/docs/test_adr_files.py` — it checks the file name, the front
   matter, the status vocabulary, the mirrored links, and that the index lists every file.

## Changing an ADR

Do not rewrite history. Write a new ADR that supersedes the old one.

The two allowed edits to an existing ADR are its `superseded_by` line, and a dated
`## Amendment` section when the change is small and additive — see
[ADR-025](0025-session-reset-tiers.md) for the one example in this repo.
