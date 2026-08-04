---
id: ADR-023
title: Scenario-Centric Architecture
status: accepted
created: 2026-07-22
supersedes: [ADR-020, ADR-022]
superseded_by: [ADR-024]
---

# ADR-023 — Scenario-Centric Architecture

## Context

RP Engine began as a character-centric roleplay bot: a user selected a `Character`, a
`Session` bound `owner + character + world`, and conversation flowed from there. The
product evolved into a scenario-based interactive-fiction engine, where the reusable unit
is a whole adventure (world + characters + rules + opening), not a single character.

The character-centric model made `Character` the root entity and coupled session identity
to a specific character. That did not support curated adventures, characterless/freeform
scenarios, or multi-character casts.

## Decision

Make the scenario the primary concept.

* `ScenarioDefinition` — a reusable, immutable blueprint: world, role profiles, characters
  (optional), rules, optional story graph, initial context.
* `ScenarioSession` — a runtime instance owned by a `user` or `group`: references a
  definition and holds all evolving state (active participants, world state, story
  progress, conversation history).
* `Character` becomes an optional asset used *within* a scenario, not the root entity.

The runtime is fully scenario-native end-to-end (Telegram adapter → `PlaythroughService`
/ `ChatService` → `ConversationBuilder`). Curated scenarios are authored as JSON in a
catalog directory (see `docs/SCENARIOS.md`) and selected with `/play`. User-facing
character creation/selection is removed from the product.

**Backward compatibility is explicitly not maintained** (the project is in beta):
pre-migration `Session` data may need to be recreated. Code was rewritten directly onto
scenario entities rather than keeping parallel legacy paths.

Both persistence backends (JSON and PostgreSQL) implement the scenario stores behind one
shared serializer and one behavioral contract suite.

## Alternatives

* Keep `Character` as the root and bolt scenarios on top — rejected: perpetuates the
  coupling this ADR removes.
* Maintain a v1 (character) and v2 (scenario) runtime side by side — rejected: doubles
  surface area for a pre-release product; the no-compat decision makes it unnecessary.

## Rationale

* Matches the product: players launch adventures, not chatbots.
* Cleanly separates immutable blueprint (`ScenarioDefinition`) from runtime state
  (`ScenarioSession`).
* Supports characterless/freeform scenarios and future multi-character casts.
* Curated JSON catalog lets developers author content without code changes.

## Consequences

### Positive

* Clean domain model with an explicit definition/runtime split.
* Curated, data-authored scenario library.
* Provider abstraction, Telegram-adapter separation, and dual persistence preserved.

### Negative

* Existing playthroughs from the character-centric era are not migrated.

### Follow-up (completed)

* The character-centric dead code was removed: legacy `Session`/`SessionStore` (+ JSON and
  PostgreSQL stores), `CharacterService`/`CharacterCommandService`, `CharacterStore` (+
  stores), `SelectCharacterCommand`, `character_card`, and the `invocation_policy` module.
  The `sessions`, `active_sessions`, and `characters` tables were dropped (Alembic
  `20260722_0004`). The `Character`/`CharacterVisibility` domain entities remain, as
  scenarios embed characters. `WorldStore` and the conversation summarizer are left in
  place but are no longer wired into the runtime.

## Supersedes

* Supersedes ADR-020 (Conversation Ownership and Identity Scope) where it made `Session`
  bind `owner + character + world`; ownership is now `ScenarioSession` → `ScenarioDefinition`.
* Narrows ADR-022 (Character Card v3): the character card remains the portable character
  asset format, but characters are now scenario assets rather than the root entity.
