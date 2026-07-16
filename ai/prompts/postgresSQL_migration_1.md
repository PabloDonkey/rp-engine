# PostgreSQL Migration — Milestone 1 (Foundation)

We are beginning the migration of the RP Engine persistence layer from JSON files to PostgreSQL.

## Context

This project follows Clean Architecture.

Current layers:

- adapters
- application
- domain
- infrastructure

The domain must remain completely independent from PostgreSQL.

PostgreSQL is an infrastructure concern.

The current JSON implementation is the reference implementation and must continue working until the migration is complete.

This migration must be performed incrementally using vertical slices.

---

# Objectives

Implement the PostgreSQL foundation without changing application behavior.

At the end of this milestone:

- JSON persistence still works.
- PostgreSQL support exists behind repository interfaces.
- No feature regressions.
- Existing tests continue passing.
- New tests are added where appropriate.

---

# Architecture Requirements

Do NOT let SQL or database concepts leak into:

- domain
- application services

Only infrastructure should know PostgreSQL exists.

Repositories should be injected through existing dependency injection/composition.

No singleton globals.

---

# Tasks

---

## 0. Local PostgreSQL Development Environment

Set up a complete local PostgreSQL development environment using Docker Compose.

Create:

- docker-compose.yml (or extend the existing one if present)
- .env.example
- .gitignore updates if needed

Requirements:

PostgreSQL:

- PostgreSQL 17 (latest stable unless project already targets another version)
- Persistent Docker volume
- Configurable database name
- Configurable username/password
- Automatic database creation
- Health check
- Automatic restart unless stopped

Expose the default PostgreSQL port:

5432

Environment variables:

POSTGRES_DB=rp_engine
POSTGRES_USER=rp_engine
POSTGRES_PASSWORD=change_me

Provide matching application configuration.

Example:

DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=rp_engine
DATABASE_USER=rp_engine
DATABASE_PASSWORD=change_me

Optional (recommended):

Add pgAdmin as a second service for local development.

Requirements:

- Connected to the PostgreSQL container
- Persistent storage
- Configurable admin credentials
- Accessible via browser

Document:

- how to start the stack
- how to stop it
- how to reset the database
- where persistent data is stored
- how to connect using psql or another SQL client

The Docker environment should require only:

docker compose up -d

to obtain a working PostgreSQL instance.

The application should be able to start after the database becomes healthy.

Do not require any manual SQL setup.

## 1. Add PostgreSQL infrastructure

Create an infrastructure package for PostgreSQL.

Example:

src/rp_engine/infrastructure/postgres/

Include:

- connection management
- configuration
- session/transaction handling
- repository implementations

Keep responsibilities separated.

---

## 2. Configuration

Extend configuration to support PostgreSQL.

Typical configuration:

- host
- port
- database
- username
- password
- ssl mode (future)
- connection pool settings if appropriate

Configuration should continue supporting JSON-only mode.

---

## 3. Repository interfaces

Review all persistence interfaces.

Ensure they are storage-agnostic.

If necessary, refactor them so they represent domain operations instead of filesystem operations.

Example:

Good:

CharacterRepository.save(character)

Bad:

write_character_json()

---

## 4. PostgreSQL repository implementations

Implement PostgreSQL versions of the repositories.

Initially they may support only the entities needed for the first migration slices.

Keep implementations small and focused.

---

## 5. Dependency injection

Update composition root.

Configuration should determine whether the application uses:

- JSON repositories
- PostgreSQL repositories

without changing business logic.

---

## 6. Database migrations

Introduce a migration system.

Preferred:

Alembic

Create the initial migration infrastructure but do not create every table yet.

Future migrations will evolve incrementally.

---

## 7. Documentation

Create:

docs/DATABASE_MODEL.md

Include:

- purpose
- architectural goals
- entity overview
- repository mapping
- migration strategy
- design principles

Do NOT duplicate DOMAIN_MODEL.md.

This document should explain how the domain maps onto PostgreSQL.

---

# Constraints

Do NOT redesign the domain model.

Use the existing documented concepts:

- User
- Character
- Character State
- Conversation
- Memory
- Visibility

Character Definition and Character State must remain separate concepts.

Ownership belongs to Character.

---

# Quality Requirements

Follow existing project conventions.

Maintain:

- SOLID
- Clean Architecture
- dependency inversion
- type hints
- dataclasses/Pydantic patterns already used
- ruff
- mypy

Avoid duplication.

Keep modules cohesive.

---

# Deliverables

Produce:

- PostgreSQL infrastructure package
- configuration support
- repository implementations
- dependency injection updates
- migration framework
- DATABASE_MODEL.md
- updated tests

Do not remove the JSON implementation.

The project should support both persistence backends during the migration.