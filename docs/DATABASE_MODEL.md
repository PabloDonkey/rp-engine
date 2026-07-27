# Database Model

## Purpose

This document describes how RP Engine domain concepts map to PostgreSQL during the JSON-to-PostgreSQL migration.

The goal is to add relational persistence behind existing repository interfaces without changing application behavior or leaking SQL concerns into domain and application layers.

## Architectural Goals

- Keep domain models storage-agnostic.
- Keep application services unaware of backend details.
- Select JSON or PostgreSQL in the composition root through configuration.
- Migrate incrementally in vertical slices while preserving JSON compatibility.

## Current Scope

Milestone 1 migrates only these repositories to PostgreSQL:

- SessionStore
- ConversationStore

Milestone 2 additionally migrates:

- CharacterStore (character definition only)

All other repositories remain on JSON in this milestone:

- WorldStore
- UserIdentityStore
- GroupIdentityStore
- GenerationTraceStore

Character State is removed as an active domain concept and has no PostgreSQL table in current scope.

JSON character persistence is card-based. Legacy `state.json` compatibility output is removed.

## Entity Overview

> **Removed tables.** The `sessions`, `active_sessions`, and `characters` tables below are
> **no longer used** and were dropped in Alembic migration `20260722_0004`. They are kept
> here only as historical documentation of the character-centric era. The live runtime
> uses `scenario_definitions`, `scenario_sessions`, `active_scenario_sessions`, and
> `conversation_messages`. See ADR-023 and `DOMAIN_MODEL.md`.

### sessions (removed)

Maps to domain Session.

Columns:

- id (UUID, PK)
- owner_kind (TEXT-like constrained value: user or group)
- owner_id (UUID)
- character_id (TEXT)
- world_id (TEXT)
- created_at (timestamptz)
- metadata (jsonb)

### active_sessions

Stores active session pointer per owner context.

Columns:

- owner_kind (PK part)
- owner_id (PK part)
- session_id (UUID, FK -> sessions.id)

### conversation_messages

Stores ordered conversation messages for one memory key.

Columns:

- id (UUID, PK)
- memory_key (TEXT)
- session_id (UUID nullable, derivable from memory_key for session scope)
- role (TEXT: system, user, character)
- content (TEXT)
- metadata (jsonb)
- created_at (timestamptz)

Message ordering is reconstructed by created_at then id.

### characters

Stores reusable Character Definitions.

Columns:

- pk (UUID, internal PK)
- character_id (TEXT, unique external/domain identifier)
- owner_id (UUID)
- visibility (TEXT enum-compatible: PRIVATE, SHARED, PUBLIC)
- name (TEXT)
- description (TEXT)
- personality (TEXT)
- greeting (TEXT)
- metadata (jsonb)
- created_at (timestamptz)
- updated_at (timestamptz)

Ownership relationship:

- One owner_id can own many character definitions.
- Visibility affects access semantics, not ownership.

JSONB usage:

- metadata stores extensible character attributes without premature table normalization.

### scenario_definitions

Stores reusable scenario blueprints (`ScenarioDefinition`).

Columns:

- id (TEXT, PK — application-owned scenario id)
- owner_id (UUID, indexed)
- name (TEXT)
- description (TEXT)
- world (JSONB, nullable — serialized `World`)
- characters (JSONB — {role: Character})
- rules (JSONB — list of strings)
- story_graph (JSONB, nullable — serialized `StoryGraph`)
- initial_context (TEXT)
- visibility (TEXT — PUBLIC, UNLISTED, RESTRICTED)
- allowed_group_chat_ids (JSONB — list of Telegram chat ids)
- metadata (JSONB)
- created_at (timestamptz)
- updated_at (timestamptz)

Nested structures (world, characters, story graph) are stored as JSONB
rather than normalized into separate tables. The same serialization
(`infrastructure/scenario_serialization.py`) is shared with `ScenarioTransferService`'s
JSON import/export, guaranteeing byte-for-byte round-trips (see ADR-024).

### scenario_sessions

Stores runtime scenario instances (`ScenarioSession`).

Columns:

- id (UUID, PK)
- scenario_definition_id (TEXT, indexed — the blueprint this session runs)
- owner_kind (TEXT: user or group)
- owner_id (UUID)
- active_participants (JSONB — {role: character_id})
- world_state (JSONB — runtime variables)
- story_progress (JSONB — narrative progress)
- created_at (timestamptz)
- metadata (JSONB)
- directives (JSONB — player directives: `{language, rules: [{id, text}], director_instruction}`)

Composite index on (owner_kind, owner_id, scenario_definition_id) backs session reuse
lookup on character selection.

`directives` is one JSONB document rather than three columns: the three controls are read
and written as a unit (the `SessionDirectives` value object), never queried individually,
and the shape is expected to grow. Rows written before migration `20260726_0008` hold
`{}`, which deserializes to the neutral defaults (`language: auto`, no rules, no pending
director instruction).

### active_scenario_sessions

Active session pointer per owner context (mirrors `active_sessions`).

Columns:

- owner_kind (PK part)
- owner_id (PK part)
- session_id (UUID, FK -> scenario_sessions.id ON DELETE CASCADE)

## Repository Mapping

- SessionStore -> PostgresSessionStore
  - get_by_id
  - find_by_relationship
  - save
  - set_active_for_owner
  - get_active_for_owner

- ConversationStore -> PostgresConversationStore
  - save_message
  - load_messages
  - clear

- CharacterStore -> PostgresCharacterStore
  - get_by_id
  - find_by_name
  - create_minimal

- ScenarioDefinitionStore -> PostgresScenarioDefinitionStore
  - get_by_id
  - find_by_owner
  - save
  - delete

- ScenarioSessionStore -> PostgresScenarioSessionStore
  - get_by_id
  - find_by_owner
  - find_by_definition
  - save
  - set_active_for_owner
  - get_active_for_owner
  - delete

PostgreSQL is the sole persistence backend (see `docs/DECISIONS.md`, ADR-024) — the composition
root (`app/main.py::build_container`) wires these repositories unconditionally. One behavioral
contract suite (`tests/unit/infrastructure/contracts/`) exercises each port against Postgres via
the testcontainers fixture in `tests/conftest.py`.

## Migration Strategy

- Alembic manages schema evolution; migrations must be reversible (`upgrade head` and
  `downgrade` both verified against a real DB).
- Curated scenarios are authored as JSON files and imported into Postgres on every boot
  (`ScenarioTransferService`, see ADR-024) rather than read live from disk.

## Design Principles

- UUID primary keys for all PostgreSQL entities.
- No domain redesign during persistence migration.
- No SQL concepts in domain entities or application use cases.
- Small, cohesive repository implementations in infrastructure.
