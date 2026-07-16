# PostgreSQL Migration — Milestone 2 (Character Persistence)

The PostgreSQL foundation is complete.

Current status:

- ✅ Clean Architecture preserved
- ✅ Repository abstraction in place
- ✅ Dependency injection selects backend
- ✅ JSON remains the default backend
- ✅ PostgreSQL is opt-in
- ✅ Docker Compose provides PostgreSQL + pgAdmin
- ✅ Alembic migrations are working
- ✅ Session and Conversation persistence have PostgreSQL implementations
- ✅ Existing tests continue to pass

The next milestone is to migrate Character persistence.

---

# Goal

Move Character Definition persistence to PostgreSQL while keeping Character State, Memory, World State, and other evolving data on JSON.

This should continue the incremental migration strategy.

No feature regressions.

No domain redesign.

---

# Architecture Requirements

Maintain Clean Architecture.

The domain and application layers must remain storage-agnostic.

Only infrastructure should know about:

- SQLAlchemy
- PostgreSQL
- Alembic

Do not leak ORM models into the domain.

Continue using repository interfaces.

---

# Scope

Migrate only Character Definition.

Do NOT migrate:

- Character State
- Memory
- World State
- Conversation State
- Relationship State
- Identity State

Those remain on the JSON backend for now.

---

# Character Model

Persist the reusable Character Definition.

Typical fields include:

- id (UUID)
- owner_id
- visibility
- name
- description
- personality
- appearance
- scenario
- rules
- system prompt
- metadata (JSONB if appropriate)
- timestamps

Do not persist evolving runtime information here.

Character Definitions are reusable templates.

---

# Ownership

Implement ownership exactly as documented.

Every Character:

- has exactly one owner
- belongs to one User
- may participate in many conversations

Future visibility must never affect ownership.

---

# Visibility

Support the documented visibility enum.

Current values:

- PRIVATE
- SHARED
- PUBLIC

Current application behavior remains PRIVATE by default.

The other values should exist in the schema for future compatibility but do not require application features yet.

---

# PostgreSQL Schema

Create a new Alembic migration.

Add the Characters table.

Use:

- UUID primary keys
- proper foreign keys
- indexes where appropriate
- created_at
- updated_at

Choose appropriate PostgreSQL types.

Use JSONB where it provides a better representation than unnecessary normalization.

Avoid over-normalizing.

---

# Repository

Implement PostgreSQL CharacterRepository.

Behavior should match the JSON repository exactly.

CRUD operations should preserve existing semantics.

Repository interface should remain unchanged whenever possible.

---

# Dependency Injection

Update composition so that:

JSON backend

uses:

JsonCharacterRepository

PostgreSQL backend

uses:

PostgresCharacterRepository

No application code should change.

---

# Repository Contract Tests

Introduce backend-independent contract tests.

The same behavioral tests should execute against:

- JSON CharacterRepository
- PostgreSQL CharacterRepository

Both implementations must satisfy identical behavior.

The objective is to ensure persistence backend never changes application semantics.

---

# Documentation

Update DATABASE_MODEL.md

Document:

- Character table
- ownership relationship
- visibility
- JSONB usage
- repository mapping

Do not duplicate DOMAIN_MODEL.md.

---

# Quality Requirements

Follow project conventions.

Maintain:

- SOLID
- dependency inversion
- repository pattern
- type hints
- mypy clean
- ruff clean

Avoid duplication.

Keep infrastructure cohesive.

---

# Validation

Before completing the milestone:

- Existing tests continue passing.
- New PostgreSQL repository tests pass.
- Alembic migration upgrades successfully.
- Alembic downgrade works correctly.
- Character CRUD behaves identically on JSON and PostgreSQL.
- Docker Compose environment continues working without manual setup.

The migration should leave the project in a fully working state with Character Definitions stored in PostgreSQL while all runtime character evolution remains on the existing JSON persistence.