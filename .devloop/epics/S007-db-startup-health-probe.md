# S007 · DB startup health probe + `/health`

**Status:** 🔵 Backlog
**Effort:** ~1-2 h
**Risk:** Low

## Context

With `postgres` backend, nothing verifies the DB is reachable or at the expected schema
version at boot:

- `app/lifespan.py` starts Telegram but never pings the DB — a bad `RP_ENGINE_POSTGRES_*`
  config fails **lazily** on the first user turn, not at startup.
- `/health` in `app/main.py` reports only `llm` and `telegram`; there is no `db` status.

## Tasks

- [ ] On startup (when backend is postgres), run a `SELECT 1` connectivity check; log clearly
      and fail fast (configurable) if the DB is unreachable.
- [ ] Optionally assert the Alembic head matches the DB's stamped revision (warn on mismatch).
- [ ] Add `db` to the `/health` payload (`available` / `unavailable` / `n/a` for JSON backend).
- [ ] Thread a lightweight DB-ping handle into the container / lifespan without leaking
      SQLAlchemy into the core (probe lives in `infrastructure/postgres`).

## Verification

- [ ] Boot with a bad DB host → clear startup error (or `/health` shows `db: unavailable`).
- [ ] Boot with JSON backend → `/health` shows `db: n/a`, no probe attempted.
- [ ] `uv run pytest` green, mypy + ruff clean.
