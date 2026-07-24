> 🗄️ **ARCHIVED — COMPLETED 2026-07-23.** Frozen; do not edit. Kept as evolution history.
> **Result:** `tests/integration/infrastructure/test_migration_integrity_postgres.py` (gated) —
> upgrade/downgrade round-trip, autogenerate drift guard, migrate-then-contract fixture running
> all 7 store contracts against a schema built by real Alembic migrations. `test_alembic_migrations.py`
> (ungated) asserts a single head. **Caught a real bug**: the drift guard found
> `GenerationTraceRecord.session_id` had `index=True` in the ORM model with no matching index in
> migration `0007` — fixed by dropping the redundant single-column index (the composite
> `(session_id, created_at)` index already covers it). Live-verified against Postgres 17: full
> gated suite 12/12 passed. Full local suite 216 passed / 12 skipped, mypy clean on `src/`
> (baseline unchanged at 48 pre-existing test/alembic-file errors), ruff clean. Also fixed an
> unrelated `alembic.ini` deprecation warning (`path_separator = os`) noticed along the way.

---

# S006 · Migration-vs-model integrity tests

**Status:** ✅ COMPLETE — archived 2026-07-23
**Effort:** ~2-3 h
**Risk:** Medium (may reveal existing model/migration drift) — **it did.**

## Context

The gated PG contract tests built the schema with **`Base.metadata.create_all`**, not the
Alembic migrations (`tests/integration/infrastructure/test_scenario_stores_contract_postgres.py`
`_prepare_engine`). So **the migrations were never exercised by any test** — a migration could
silently diverge from the ORM models and nothing would catch it. The deployed schema comes from
`alembic upgrade head`; the tests validated a *different* schema.

## Tasks

- [x] **Round-trip test** (gated, `test_migration_upgrade_downgrade_round_trip`): on a scratch
      DB (`DROP SCHEMA public CASCADE` / `CREATE SCHEMA public` for a truly clean slate, not
      relying on an existing `alembic_version` stamp), `alembic upgrade head` then
      `downgrade base`, asserting no model tables remain, then `upgrade head` again and
      asserting all model tables exist.
- [x] **Migrate-then-contract** (`test_migrate_then_contract_all_stores`): a `migrated_engine`
      fixture prepares the PG schema via `alembic upgrade head` (not `create_all`), and all 7
      store contracts (scenario definition + minimal round-trip, scenario session, conversation,
      user identity, group identity, generation trace) run against it.
- [x] **Autogenerate drift guard** (`test_migrations_match_models_with_no_autogenerate_drift`):
      `alembic.autogenerate.compare_metadata` against a migrated connection, asserting an empty
      diff. **Found real drift** on first run: `GenerationTraceRecord.session_id` was declared
      `index=True` in `models.py`, but migration `20260723_0007` only created the composite
      `ix_generation_traces_session_created` index, not a standalone `session_id` index. Fixed
      by removing `index=True` from the model (the composite index's leftmost column already
      serves single-column `session_id` lookups) rather than adding a redundant index to the
      migration.
- [x] Confirmed single head after S004's `0007`: `test_alembic_has_a_single_head` (ungated unit
      test, no DB needed — inspects `ScriptDirectory.get_heads()` directly) plus a live
      `alembic heads` check during manual verification.

## Verification

- [x] Live-verified against a real Postgres 17 container (dev box's docker-compose Postgres
      couldn't bind port 5432 — held by a host `postgresql` systemd service with no sudo access
      in this environment — so verification used a standalone container on a throwaway port,
      same workaround as S004/S005): gated suite `tests/integration/infrastructure/` —
      12/12 passed (4 migration-integrity tests + 8 from S004/S005).
- [x] `alembic upgrade head && alembic downgrade base` succeeds against the real DB.
- [x] `uv run pytest` green: 216 passed, 12 skipped. mypy clean on `src/` (repo-wide count
      unchanged from the 48-error pre-existing baseline in `tests/`/`alembic/`). ruff clean.
