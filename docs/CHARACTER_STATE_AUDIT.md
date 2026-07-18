# Character State Audit and Migration Plan

Date: 2026-07-17
Status: Completed and Implemented
Scope: Repository-wide architecture and implementation audit for Character State usage.

## Phase 1 Audit Summary

Question 1. Is Character State actively used by the engine?
Answer: No. There is no runtime domain entity, repository interface, or service flow that reads or mutates a structured Character State model.

Question 2. Is it referenced by prompt generation?
Answer: No. Prompt assembly is driven by Character definition, World lore, roleplay rules, and conversation memory history.

Question 3. Is it modified during conversations?
Answer: No. Conversation turns append user/character messages to conversation storage only.

Question 4. Is it consumed by application services?
Answer: No. Application services load Session, User/Group, Character, World, and conversation history. No Character State object is loaded.

Question 5. Is it only persisted but never used?
Answer: Historical only. During audit, JSON backend character creation still wrote a compatibility `state.json` file that was not consumed by runtime logic. This artifact has now been removed.

Question 6. Which files are affected if Character State were removed?
Answer: See inventory below. Main impact areas are documentation and JSON character creation compatibility artifacts.

## Evidence Highlights

### Runtime conversation path (active)

- `src/rp_engine/application/services/chat_service.py`
  - Loads session context via Session, Character, World stores.
  - Builds conversation context from conversation history memory strategy.
  - No Character State read/write path.
- `src/rp_engine/core/conversation/builder.py`
  - System prompts include character definition, world info, roleplay rules, and memory hint.
  - No Character State model included.

### Historical compatibility path (removed)

- `src/rp_engine/infrastructure/storage/json_character_store.py`
  - Previously wrote `card.json` and `state.json` in `create_minimal(...)`.
  - No method read `state.json`.
  - `state.json` write path removed.
- `tests/unit/infrastructure/test_json_character_store.py`
  - Updated to verify character card persistence only.

### PostgreSQL path

- `src/rp_engine/infrastructure/postgres/models.py`
  - No character_state table.
- `alembic/versions/20260715_0001_postgres_foundation.py`
- `alembic/versions/20260715_0002_character_definition_postgres.py`
  - No Character State migration exists.

## Phase 4 Code Audit Inventory

Classification legend:
- actively used
- persistence only
- unused
- obsolete after ADR

### Domain objects

- Structured Character State domain object: none found.
  - Classification: unused (not implemented).
- `src/rp_engine/core/character/character.py` (Character definition model).
  - Classification: actively used.

### Repository interfaces

- `src/rp_engine/core/ports/character_store.py`
  - Character definition operations only.
  - Classification: actively used.
- Character State repository interface: none found.
  - Classification: unused (not implemented).

### JSON persistence

- `src/rp_engine/infrastructure/storage/json_character_store.py` writes `card.json` in `create_minimal(...)`.
  - Classification: actively used.
- `tests/unit/infrastructure/test_json_character_store.py` validates card persistence.
  - Classification: actively used.

### PostgreSQL models and migrations

- `src/rp_engine/infrastructure/postgres/models.py` and Alembic migrations define sessions, active_sessions, conversation_messages, characters.
  - Classification: actively used.
- Character State Postgres schema/migration: none.
  - Classification: unused (not implemented).

### Dependency injection and composition

- `src/rp_engine/app/main.py` wires CharacterStore, SessionStore, ConversationStore, WorldStore, and ChatService.
  - Classification: actively used.
- No Character State service/store wiring.
  - Classification: unused (not implemented).

### Prompt builder and orchestrator

- `src/rp_engine/core/conversation/builder.py`
- `src/rp_engine/core/engine/orchestrator.py`
- `src/rp_engine/application/services/chat_service.py`
  - Classification: actively used.
  - Character State usage: none.

### Documentation and planning text

- `docs/DOMAIN_MODEL.md`
- `docs/ARCHITECTURE.md`
- `docs/SPEC.md`
- `docs/ROADMAP.md`
- `docs/VISION.md`
- `README.md`
  - Classification: obsolete after ADR if still referring to active Character State.

## Migration Plan

### Stage 0 (now): Documentation and ADR alignment

- Adopt ADR-021 Defer Character State.
- Update architecture/spec/domain docs to reflect card + memory + lore runtime model.
- Keep compatibility artifacts untouched in code.

### Stage 1 (safe deprecation path)

- Completed.
- Compatibility-only `state.json` behavior was verified as unused.

### Stage 2 (guarded removal)

- Completed.
- Removed `state.json` write from `JsonCharacterStore.create_minimal(...)`.
- Updated tests that asserted `state.json` existence.
- Added ADR update reflecting removal as a domain concept.

### Stage 3 (future deterministic state introduction, only if justified)

Precondition: concrete feature requiring deterministic runtime mechanics.

- Introduce a focused `CharacterRuntimeState` model with explicit bounded scope.
- Add repository interface and migrations only for required fields.
- Keep prompt usage explicit and minimal.
- Add a new ADR for model boundaries and ownership.

## Backward Compatibility Position

Current recommendation: do not reintroduce compatibility `state.json` writes unless a concrete migration requirement appears.

Authoritative runtime continuity today:
- Character Definition (card)
- Session conversation memory
- World lore
