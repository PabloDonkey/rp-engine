> 🗄️ **ARCHIVED — COMPLETED 2026-07-23.** Frozen; do not edit. Kept as evolution history.
> **Result:** `PostgresUserIdentityStore`/`PostgresGroupIdentityStore`/`PostgresGenerationTraceStore`
> added under `postgres/repositories/`; migration `20260723_0007` adds `users`,
> `user_identities`, `groups`, `group_identities`, `generation_traces`; `build_container` wires
> all three into the `postgres` branch. Shared `infrastructure/identity_serialization.py` used by
> both JSON and PG stores. New contract-test suite (unit JSON + gated PG) passes; live-verified
> against a real Postgres 17 container: `alembic upgrade head` / `downgrade` round-trips clean,
> all 5 gated PG contract tests pass. Full suite 217 passed / 5 skipped, mypy clean on `src/`,
> ruff clean.

---

# S004 · PG parity for identity + generation-trace stores

**Status:** ✅ COMPLETE — archived 2026-07-23
**Effort:** ~4-6 h
**Risk:** Medium (new tables + migration + serializer parity across two backends)

## Context

This is the **core gap** for "finishing the PG integration." Three ports had **no
Postgres implementation**, so even with `RP_ENGINE_PERSISTENCE_BACKEND=postgres` the
composition root (`app/main.py` `build_container`) hard-wired JSON for them:

- `GenerationTraceStore` → `JsonGenerationTraceStore`
- `UserIdentityStore`     → `JsonUserIdentityStore`
- `GroupIdentityStore`    → `JsonGroupIdentityStore`

Result: a "postgres" deployment still read/wrote JSON files on local disk for traces and
identity mappings — the app was **not** actually single-backend and could not run statelessly.

## Tasks

- [x] **Models** — added SQLAlchemy records in `infrastructure/postgres/models.py`:
  - [x] `users` + `user_identities` (composite PK `(provider, external_id)`, FK to `users.id`).
        Design note: went with a normalized 2-table shape per entity (`users`/`user_identities`,
        `groups`/`group_identities`) rather than one flat table — `UserIdentityStore`/
        `GroupIdentityStore` support multiple identities per user/group (tuple in the domain
        model), which a single-table shape can't represent without denormalizing the profile.
  - [x] `groups` + `group_identities`, same shape.
  - [x] `generation_traces` (trace id, session_id, `record` JSONB, `created_at`); the port is
        append-only so there's no memory-key/prompt-response column split to match.
  - [x] Column names/nullability match the JSON serializer's normalized output.
- [x] **Migration** — `alembic/versions/20260723_0007_identity_trace_tables.py`
  - [x] `create_table` for all five tables (`users`, `user_identities`, `groups`,
        `group_identities`, `generation_traces`); indexes on `user_id`/`group_id`/
        `(session_id, created_at)`.
  - [x] Verified `upgrade head` **and** `downgrade` against a real Postgres 17 container
        (docker run on a throwaway port, since the dev box's `docker-compose.yml` port 5432
        was already held by a host-level `postgresql` systemd service — no sudo available to
        stop it, so verification used a standalone container instead).
- [x] **Serializer parity** — added `infrastructure/identity_serialization.py` (sibling shared
      serializer module, since `scenario_serialization.py` is scenario-specific) with
      `normalize_identity_metadata`/`identity_from_payload`; refactored both JSON stores
      (`json_user_identity_store.py`, `json_group_identity_store.py`) to use it instead of
      inline duplicated dict-filtering, so JSON and PG normalize identity metadata identically.
- [x] **Postgres stores** — `PostgresUserIdentityStore`, `PostgresGroupIdentityStore`,
      `PostgresGenerationTraceStore` under `postgres/repositories/`, exported from
      `repositories/__init__.py` and `postgres/__init__.py`.
- [x] **Wire composition root** — `build_container` now selects all three identity/trace stores
      inside the `persistence_backend == "postgres"` branch, alongside the scenario/conversation
      stores.
- [x] **Contract tests** — `tests/unit/infrastructure/contracts/{user_identity,group_identity,
      generation_trace}_store_contract.py`, run via a JSON unit runner
      (`test_identity_trace_stores_contract_json.py`) and a gated PG integration runner
      (`test_identity_trace_stores_contract_postgres.py`), mirroring the scenario-store pattern.

## Bug found + fixed during live PG verification

The first PG run failed both identity contract tests with a `ForeignKeyViolationError`:
`UserRecord`/`GroupRecord` and their identity rows have no ORM `relationship()` between them
(intentionally — the domain model doesn't need one), so SQLAlchemy's unit-of-work has no
dependency processor to order the flush, and `session.new` is a hash set — insert order isn't
guaranteed to match `session.add()` call order. Fixed by adding an explicit
`await db_session.flush()` between adding the parent row and the identity row in both
`PostgresUserIdentityStore.create_user_with_identity` and
`PostgresGroupIdentityStore.create_group_with_identity`.

## Verification

- [x] `uv run pytest` green: 217 passed, 5 skipped (PG-gated tests skip without
      `RP_ENGINE_RUN_POSTGRES_TESTS=1`).
- [x] `uv run mypy .` — `src/` clean (103 files); the new migration's `sa.dialects.postgresql.JSONB`
      untyped-call warning matches the pre-existing pattern in every prior migration file
      (baseline was already 48 mypy errors under `tests/`/`alembic/`, unrelated to this change).
- [x] `uv run ruff check .` clean.
- [x] Manual, against a real Postgres 17 container: `alembic upgrade head` and `downgrade` to
      `20260722_0006` and back both succeed; `RP_ENGINE_RUN_POSTGRES_TESTS=1` gated suite —
      5/5 passed, including the two that caught the flush-order bug above.
