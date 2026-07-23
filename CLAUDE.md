# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Package manager is **uv**. Python 3.12+.

```bash
uv sync                              # install deps (incl. dev group)
uv run pytest                        # run all tests (JSON backend; PG tests skip)
uv run pytest tests/unit/core/conversation/test_builder.py   # single file
uv run pytest -k "resume"            # single test by name substring
uv run ruff check .                  # lint
uv run ruff format .                 # format (double quotes, line-length 100)
uv run mypy .                        # type check (strict mode)
uv run alembic upgrade head          # apply DB migrations
```

Run the app (FastAPI + Telegram):

```bash
uv run python -m uvicorn --app-dir src rp_engine.app.main:app --reload --host 0.0.0.0 --port 8000
```

### PostgreSQL-backed tests

PG integration/contract tests are **gated** and skip unless the DB is up and a flag is set.
Use the project venv's pytest, not a system one (missing `fastapi`/`telegram`/`lmstudio`
imports = wrong interpreter):

```bash
scripts/db_services.sh up            # start postgres + pgAdmin (docker compose)
scripts/test_postgres.sh             # one-shot: starts DB + runs the full suite with PG on
RP_ENGINE_RUN_POSTGRES_TESTS=1 uv run pytest tests/integration/infrastructure/   # PG store contracts only
```

Before finishing a nontrivial change, the bar is: **`uv run pytest` green, `uv run mypy .`
clean, `uv run ruff check .` clean.** `src/` is expected to be fully mypy-clean.

## Architecture

Hexagonal / ports-and-adapters, layered so the **core never imports a framework**
(no Telegram, FastAPI, LM Studio, SQLAlchemy in `core/`). Dependencies point inward.

```
adapters/  →  application/  →  core/ (engine, domain, ports)
                                   ↑
                          infrastructure/ (implements core ports)
```

- **`core/ports/`** — Protocol interfaces the core depends on (`LLMProvider`,
  `ConversationStore`, `ScenarioDefinitionStore`, `ScenarioSessionStore`, …). Everything
  the domain needs from the outside world is a port; `infrastructure/` provides the impls.
- **`core/`** — domain + engine. Domain entities are **immutable** (`frozen=True` dataclasses
  with factory methods). `core/engine/orchestrator.py` (`RPOrchestrator`) drives a turn;
  `core/conversation/builder.py` (`ConversationBuilder`) turns scenario context into the
  LLM prompt (templates `{{char}}`/`{{user}}`/`{{world}}`, scenario rules, initial context).
- **`application/services/`** — use-case orchestration. `PlaythroughService` (scenario
  catalog → start/resume/restart a playthrough) and `ChatService` (send/continue/retry a
  turn) are the primary entry points the adapters call.
- **`adapters/`** — `telegram/` and `api/`. Transport concerns live here: slash-command
  parsing, **authorization/invocation policy**, message splitting. Adapters hold no business
  logic. Telegram is the primary, fully-featured surface.
- **`infrastructure/`** — port implementations: `llm/lmstudio/`, `postgres/` (SQLAlchemy
  async + Alembic), `storage/` (JSON files), `catalog/` (`ScenarioCatalog` loads curated
  scenario JSONs), `config/settings.py` (pydantic-settings, `RP_ENGINE_`-prefixed env).
- **`app/main.py`** is the **composition root** — the only place that wires concrete
  implementations to ports and picks the backend from `RP_ENGINE_PERSISTENCE_BACKEND`
  (`json` | `postgres`).

### Domain model: scenario-centric

The engine is **scenario-native**: `User → ScenarioDefinition → ScenarioSession →
Conversation`. A `ScenarioDefinition` is an immutable blueprint (world, characters, rules,
opening); a `ScenarioSession` is a per-owner runtime instance. `Character` is an *optional*
embedded asset, not a root entity. There is **no v1 backward compatibility** — the old
character-centric `Session` model was fully removed (see `docs/DECISIONS.md` ADR-023).

### Dual persistence backends

JSON and PostgreSQL are kept at **parity** via a shared serializer
(`infrastructure/scenario_serialization.py`) and **one contract-test suite run against both
backends** (`tests/.../contracts/`). Changing storage semantics means updating the shared
serializer and keeping both runners green. PG schema changes require an Alembic migration
that is **reversible** (verify `upgrade head` *and* `downgrade` against a real DB).

## Documentation map

Substantial design docs live in `docs/` — read the relevant one before large changes:

| Doc | For |
|---|---|
| `docs/ARCHITECTURE.md` | layer responsibilities, dependency rules, command flows |
| `docs/DOMAIN_MODEL.md` | domain entities and terminology |
| `docs/DATABASE_MODEL.md` | PostgreSQL tables ↔ repository mapping |
| `docs/DECISIONS.md` | ADRs (ADR-023 = the scenario pivot) |
| `docs/SCENARIOS.md` | scenario catalog JSON authoring guide |
| `docs/ROADMAP.md` | milestones |

## Dev-loop tracking (`.devloop/`)

Local, **gitignored** execution tracking (not the committed `docs/`):

- `.devloop/BOARD.md` — kanban (VSCode "Markdown Kanban" extension), the glance view.
- `.devloop/epics/S###-<slug>.md` — one checklist per active epic. Each epic has a stable,
  incremental **story id** `S###` (assigned at creation, persists into the archive).
- `.devloop/archive/S###-YYYY-MM-DD-<slug>.md` — frozen, completed epics; **never edit**.

When starting/finishing a unit of work, follow `.devloop/README.md`: create/move the epic
file, take the next `S###`, and move its board card between columns. Next story number:
`ls .devloop/epics .devloop/archive | grep -oE 'S[0-9]+' | sort -u | tail -1`.
