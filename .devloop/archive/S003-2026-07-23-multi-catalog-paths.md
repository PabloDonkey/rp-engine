> 🗄️ **ARCHIVED — COMPLETED 2026-07-23.** Frozen; do not edit. Kept as evolution history.
> **Result:** `scenario_catalog_dir: str` → `scenario_catalog_dirs: list[str]` (comma-delimited
> env parsing); `ScenarioCatalog.from_directories(...)` merges dirs with later-wins on id
> collision; `.env.example`/README/SCENARIOS.md updated. Full suite 214 passed / 2 skipped,
> mypy clean on `src/`, ruff clean.

---

# S003 · Multiple scenario catalog paths + fix `.env.example`

**Status:** ✅ COMPLETE — archived 2026-07-23  
**Effort:** ~1-2 h  
**Risk:** Low-Medium (config shape change + a loader that merges dirs)

## Context

Two related gaps around scenario catalog configuration:

1. **`.env.example` is missing catalog config.** There is no `RP_ENGINE_SCENARIO_CATALOG_DIR`
   line, even though `settings.scenario_catalog_dir` (default `data/catalog`) exists and
   drives `ScenarioCatalog.from_directory(...)` in `app/main.py:106`. New users can't
   discover the setting.
2. **Only one catalog dir is supported.** `scenario_catalog_dir: str` is a single path.
   We want to load scenarios from **more than one** directory (e.g. curated + local/private
   catalogs) and merge them into one catalog.

## Tasks

- [x] Change the setting to accept multiple paths
  - [x] `settings.py`: `scenario_catalog_dir: str` → `scenario_catalog_dirs: list[str]`,
        parsed from a comma-delimited env value via a `field_validator(mode="before")`.
        Chose `,` over `os.pathsep` since a colon collides with Windows drive letters and
        `,` reads clearly in a `.env` file.
  - [x] Kept the default (`["data/catalog"]`).
- [x] Update the loader to merge directories
  - [x] `ScenarioCatalog` gains `from_directories([...])`; `from_directory` now delegates
        to a shared `_load_directory` helper. Collision rule: **later directory wins**
        (dict-comprehension insertion order in `__init__` already does this) — so a
        local/private catalog listed after the curated one can override a curated
        scenario. Documented in the classmethod docstring and `docs/SCENARIOS.md`.
  - [x] Updated `app/main.py:106` to pass `settings.scenario_catalog_dirs`.
- [x] Fix `.env.example`
  - [x] Added a `# Scenarios` block documenting `RP_ENGINE_SCENARIO_CATALOG_DIRS`,
        the comma delimiter, the collision rule, and the default.
  - [x] Audited `.env.example` against `settings.py` — also added the other two
        undocumented vars found: `RP_ENGINE_DEFAULT_WORLD_ID` and
        `RP_ENGINE_TELEGRAM_AUTHORIZATION_DIR` (plus a commented-out mention of
        `RP_ENGINE_TELEGRAM_UNAUTHORIZED_MESSAGE`, left commented since its default is a
        multi-line message).
- [x] Docs
  - [x] `README.md` (env var table + scenario-authoring paragraph) and
        `docs/SCENARIOS.md` ("The catalog" section) updated for multi-catalog support.

## Verification

- [x] Unit tests: `scenario_catalog_dirs` parses a comma-delimited string, accepts a list,
      defaults to `["data/catalog"]`, and rejects an empty value
      (`tests/unit/infrastructure/test_settings.py`).
- [x] Unit tests: `ScenarioCatalog.from_directories` merges scenarios from 2 dirs, and the
      later directory wins on an id collision (`tests/unit/infrastructure/test_scenario_catalog.py`).
- [x] Full suite green (214 passed, 2 skipped — PG), mypy clean on `src/`, ruff clean.
