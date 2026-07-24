# S006 · Migration-vs-model integrity tests

**Status:** 🔵 Backlog
**Effort:** ~2-3 h
**Risk:** Medium (may reveal existing model/migration drift)

## Context

The gated PG contract tests build the schema with **`Base.metadata.create_all`**, not the
Alembic migrations (`tests/integration/infrastructure/test_scenario_stores_contract_postgres.py`
`_prepare_engine`). So **the migrations are never exercised by any test** — a migration can
silently diverge from the ORM models (e.g. the access-control columns added in `0005`) and
nothing catches it. The deployed schema comes from `alembic upgrade head`; the tests validate
a *different* schema.

## Tasks

- [ ] **Round-trip test** (gated): on a scratch DB, `alembic upgrade head` then `downgrade base`
      cleanly, asserting no error and (after head) all expected tables exist.
- [ ] **Migrate-then-contract**: add a fixture variant that prepares the PG schema via
      `alembic upgrade head` instead of `create_all`, and run the store contracts against it —
      so contracts validate the *real* deployed schema.
- [ ] **Autogenerate drift guard** (optional but cheap): assert `alembic revision --autogenerate`
      produces an empty diff against `Base.metadata` (models ≡ head).
- [ ] Confirm single head after S004's `0007` (`alembic heads` shows one).

## Verification

- [ ] `scripts/test_postgres.sh` green with new migration tests active.
- [ ] `alembic upgrade head && alembic downgrade base` succeeds against a real DB.
- [ ] mypy + ruff clean.
