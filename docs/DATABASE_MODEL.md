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

### sessions

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

The same interfaces are implemented by JSON stores. The composition root decides which implementation to wire.

## Migration Strategy

- JSON remains default backend.
- PostgreSQL is opt-in through RP_ENGINE_PERSISTENCE_BACKEND=postgres.
- Alembic manages schema evolution.
- Initial migration creates only session and conversation tables.
- Future slices migrate additional repositories incrementally.

## Design Principles

- UUID primary keys for all PostgreSQL entities.
- No domain redesign during persistence migration.
- No SQL concepts in domain entities or application use cases.
- Small, cohesive repository implementations in infrastructure.
- Backward compatibility with existing JSON data flows during migration window.
