> 🗄️ **ARCHIVED — COMPLETED 2026-07-23.** Frozen; do not edit. Kept as evolution history.
> **Result:** `infrastructure/postgres/health.py` (`PostgresHealthProbe`: `ping()` + best-effort
> `check_schema_version()` warning on Alembic head mismatch). Wired into `app/lifespan.py` via a
> `DbHealthProbeProtocol` (no SQLAlchemy import needed there) — fails fast by default on an
> unreachable DB (new `RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST`, default `true`), or logs and
> continues when disabled. `/health` gained a `db` key (`available`/`unavailable`/`n/a`).
> Live-verified against a real Postgres 17: app boots, `/health` reports `available`; downgrading
> one migration step live-fired the schema-drift warning without blocking startup. Full suite
> 221 passed / 12 skipped, mypy clean on `src/`, ruff clean. `.env.example`/README updated.

---

# S007 · DB startup health probe + `/health`

**Status:** ✅ COMPLETE — archived 2026-07-23
**Effort:** ~1-2 h
**Risk:** Low

## Context

With `postgres` backend, nothing verified the DB was reachable or at the expected schema
version at boot:

- `app/lifespan.py` started Telegram but never pinged the DB — a bad `RP_ENGINE_POSTGRES_*`
  config failed **lazily** on the first user turn, not at startup.
- `/health` in `app/main.py` reported only `llm` and `telegram`; there was no `db` status.

## Tasks

- [x] On startup (when backend is postgres), run a `SELECT 1` connectivity check
      (`PostgresHealthProbe.ping()`); log clearly and fail fast (configurable via the new
      `postgres_startup_check_fail_fast` setting, default `True`) if the DB is unreachable —
      raises `RuntimeError` from the lifespan startup, which FastAPI/uvicorn surface as a
      startup failure.
- [x] Assert the Alembic head matches the DB's stamped revision, warn (never raise) on mismatch
      — `PostgresHealthProbe.check_schema_version()`, reading `alembic_version` and comparing
      to `ScriptDirectory.get_heads()`; silently no-ops if `alembic.ini` can't be found (keeps
      it best-effort in deployment contexts where the migrations directory isn't co-located).
- [x] Added `db` to the `/health` payload: `available` (ping succeeds), `unavailable` (ping
      fails but fail-fast is off), `n/a` (JSON backend, no probe attempted). Pings live on every
      `/health` call rather than caching the startup result.
- [x] Threaded a lightweight DB-ping handle into the container/lifespan without leaking
      SQLAlchemy into `app/lifespan.py`: a `DbHealthProbeProtocol` (`ping`/`check_schema_version`)
      alongside the existing `TelegramRuntimeProtocol` pattern; the concrete
      `PostgresHealthProbe` lives in `infrastructure/postgres/health.py`.

## Verification

- [x] Unit: `tests/unit/app/test_main_endpoints.py` — fail-fast startup raises `RuntimeError`
      against an unreachable host (`127.0.0.1:1`, connection-refused-fast, no real DB needed);
      non-fail-fast boots and `/health` reports `unavailable`; JSON backend reports `n/a`.
      `tests/unit/app/test_lifespan.py` — direct fake-probe coverage of the three lifespan
      branches (reachable + schema check, unreachable + fail-fast raises, unreachable +
      continues).
- [x] Manual, against a real Postgres 17 container: booted the actual uvicorn app with
      `persistence_backend=postgres` — `/health` returned `db: available`, log showed
      "PostgreSQL connectivity check passed", no drift warning (DB at head). Downgraded the DB
      one migration step live and rebooted — `/health` still `available`, but the schema-drift
      warning fired as expected, and startup was not blocked (matches "warn on mismatch").
- [x] `uv run pytest` green: 221 passed, 12 skipped. mypy clean on `src/`; ruff clean.
- [x] `.env.example` and `README.md` updated with `RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST`.
