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
- metadata (JSONB — {key: string or list of strings}; see `DOMAIN_MODEL.md`)
- created_at (timestamptz)
- updated_at (timestamptz)
- deleted_at (timestamptz, NULL — **null = the scenario is active**; set when it is
  retired. Added by `20260811_0013` (S030))

Nested structures (world, characters, story graph) are stored as JSONB
rather than normalized into separate tables. The same serialization
(`infrastructure/scenario_serialization.py`) is shared with `ScenarioTransferService`'s
JSON import/export, guaranteeing byte-for-byte round-trips (see ADR-024).

`deleted_at` is the one column that serialization does **not** carry. The store stamps it
after it builds the domain object, and an export leaves it out. A transfer file describes a
scenario, not that scenario's life inside one database.

Only `delete()` and `restore()` write this column. `save()` never touches it, and the
insert statement leaves it out of both the values and the conflict update. The reason is
the boot import: it saves every catalog file at every start, so a save that carried the
stamp would un-retire a curated scenario at the next restart.

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
- created_at (timestamptz — insert-only; deliberately absent from the upsert's SET clause)
- updated_at (timestamptz, NOT NULL — stamped by the repository on every `save`)
- deleted_at (timestamptz, NULL — **null = the live session**; set when a reset supersedes it)
- metadata (JSONB)
- directives (JSONB — player directives: `{language, rules: [{id, text}], director_instructions: [str]}`,
  plus `memory: {enabled_sources: [str]}` since S022 — see below)
- user_persona_name (VARCHAR(128), NULL — the player's character; what `{{user}}` resolves to)
- user_persona_description (TEXT, NULL — rendered as the prompt's `[User Persona]` section)

Composite index on (owner_kind, owner_id, scenario_definition_id) backs session reuse
lookup on character selection. Since migration `20260727_0009` it is **partial**
(`WHERE deleted_at IS NULL`) — every hot lookup asks for the owner's live session — and
since `20260727_0010` it is also **unique**. "One live session per owner per scenario" is
the invariant `find_by_definition` has always assumed; with duplicates it is a coin flip
between the current story and a retired one, which is what made `/play <id>` resurrect
pre-restart transcripts. `PlaythroughService` cannot legitimately create a second live row
(`_begin` runs only when none exists, or after `_reset` has stamped the outgoing session),
so the constraint costs nothing and converts a silent wrong answer into a loud failure.
`ScenarioTransferService.import_session` is the one caller that can hit it in normal use;
the admin route turns that into a 409.

`directives` is one JSONB document rather than three columns: the three controls are read
and written as a unit (the `SessionDirectives` value object), never queried individually,
and the shape is expected to grow. Rows written before migration `20260726_0008` hold
`{}`, which deserializes to the neutral defaults (`language: auto`, no rules, no pending
director notes).

The shape growing is not free: migration `20260802_0011` converted the single
`director_instruction` string into a `director_instructions` array when `/director` notes
started stacking. JSONB needs no DDL for that, but it does need the **data** converted — a
row left in the old shape reads back as an empty queue and the player's armed note vanishes
on the next load. Changing a key inside this document is a migration, not just a serializer
edit.

The persona is **two real columns**, not a JSONB bag: it is schema-visible identity with an
"immutable once set" contract, and one of the two fields is what every `{{user}}` in every
prompt resolves to. Migration `20260727_0009` added them nullable with no backfill — a null
name means "no persona", i.e. today's transport-display-name behavior.

`updated_at` is written by `PostgresScenarioSessionStore.save()` rather than by a column
`onupdate=`, which would silently never fire: this store writes via
`INSERT ... ON CONFLICT DO UPDATE`, and SQLAlchemy's `onupdate` only applies to ORM/Core
`UPDATE` statements. `save()` therefore returns the *stamped* session, not its argument.
Migration `20260727_0009` backfilled existing rows from `created_at`, not `now()`, so the
column never claims a historical session was touched on migration day.

**`20260727_0010` backfilled `deleted_at`.** 0009 left it NULL everywhere, which was right
for the column and wrong for the data: every session orphaned by a pre-S016 `/restart` was
still "live", so the resurrection bug survived in the rows even though the code was fixed.
0010 keeps exactly one session live per (owner, scenario) — chosen by the owner's active
pointer, then the most recent conversation message, then creation time — and stamps the rest
with their own last sign of life rather than `now()`. Its `downgrade` restores the
non-unique index but deliberately leaves the backfill in place: un-stamping would have to
un-stamp genuinely superseded sessions too.

### active_scenario_sessions

Active session pointer per owner context (mirrors `active_sessions`).

Columns:

- owner_kind (PK part)
- owner_id (PK part)
- session_id (UUID, FK -> scenario_sessions.id ON DELETE CASCADE)

## The memory tables (ADR-026)

> `session_summaries` exists (S023). The rest of this section is still the schema the later
> memory layers will add, recorded in S021 so each epic does not invent its own. See ADR-026 and
> `docs/MEMORY.md`.

**`MemorySettings` adds no column** (shipped in S022). It rides inside the `directives` JSONB
document, under a `memory` key, for the reason `directives` is one document in the first place:
it is read and written as one value object and never queried field by field. The two share a
column because they share a lifecycle — both are player-owned state under ADR-025, so
`/restart` carries both and `/clear` resets both. A row written before S022 has no `memory`
key and loads with the default layers. The warning above still applies: changing a key inside
that document is a migration, not just a serializer edit.

### session_summaries — layer 01, added by `20260810_0012` (S023)

One row per session. Holds the running "story so far" and the watermark that says how far it
reaches. Written only by the background worker; read on every turn by `RollingSummarySource`.

- session_id (UUID, PK, FK -> scenario_sessions.id ON DELETE CASCADE)
- summary (TEXT)
- covers_through_turn (INTEGER — narrator replies folded in, the same clock the messages'
  `turn` metadata uses)
- tokens (INTEGER — the summary's own token cost)
- model_name (VARCHAR(255) — which model wrote it, so a model swap is visible)
- created_at, updated_at (timestamptz)

`covers_through_turn` is the load-bearing column. It is both the window's floor and the answer
to the background worker's question "is this session's summary behind?". Without it the job
would have to carry the message list, which ADR-026 forbids.

`PostgresSessionSummaryStore.save()` is an `INSERT ... ON CONFLICT DO UPDATE` that leaves
`created_at` alone: the recap is one long-lived value that is rewritten, not a version per pass.
No history of the recap is kept, because the transcript it was made from already is one. The
cascade means deleting a session takes its recap with it — a recap without its transcript is a
claim about a story nobody can check.

### lorebook_entries — layer 02, S024

Authored facts, matched by trigger key. Scoped to a scenario definition, so every session of a
scenario shares one lorebook.

- id (UUID, PK)
- scenario_definition_id (TEXT, indexed, FK -> scenario_definitions.id)
- keys (TEXT[] — the trigger keys)
- content (TEXT)
- priority (INTEGER — feeds `MemoryFragment.priority`)
- enabled (BOOLEAN)
- search_vector (TSVECTOR, GIN index — stemmed matching over `keys`)
- created_at, updated_at (timestamptz)

Ranking happens in the repository, through `LorebookStore.find_matching(keywords)`. That is a
deliberate exception to ADR-013's storage-versus-selection split, recorded in ADR-026. The
alternative is loading the whole table into Python to rank it there.

### memory_facts and memory_fact_watermarks — layer 03, S025

Extracted facts with validity windows. Append only.

`memory_facts`:

- id (UUID, PK)
- session_id (UUID, indexed, FK -> scenario_sessions.id ON DELETE CASCADE)
- subject, predicate, object (TEXT — the slot a conflict is resolved on)
- source_turn (INTEGER — the turn it was extracted from)
- valid_from (timestamptz)
- invalid_at (timestamptz, NULL — null means "still true")
- superseded_by (UUID, NULL, FK -> memory_facts.id)
- created_at (timestamptz)

A fact is never deleted and never updated in place. It is stamped `invalid_at` and pointed at
whatever replaced it. This is ADR-026 implementation rule 6.

`memory_fact_watermarks` records how far extraction has run per session, so the background
worker can ask "which turns have no facts yet?" instead of being told which turns to process.

- session_id (UUID, PK, FK -> scenario_sessions.id ON DELETE CASCADE)
- extracted_through_turn (INTEGER)
- updated_at (timestamptz)

### Layer 04 — deferred

Semantic recall needs pgvector, which means new Postgres images for both docker compose and the
testcontainers fixture, plus a second resident embedding model. ADR-026 defers it to S026 and
only if a concrete failure demands it. The `EmbeddingProvider` port is designed now so that
arriving there is a migration and an adapter, not a redesign.

### Considered and not needed yet: a token count column

Decision 2 in ADR-026 caches token counts per message. The first implementation keeps that cache
in memory, keyed by message id and model name, and recounts after a restart. A `token_count`
column on `conversation_messages` would make it survive a restart, at the cost of a migration
and a value that goes stale on every model swap. Add it only if the first turn after a restart
measurably hurts.

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

PostgreSQL is the sole persistence backend (see `docs/adr/`, ADR-024) — the composition
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
