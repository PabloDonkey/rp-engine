# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Package manager is **uv**. Python 3.12+.

```bash
uv sync                              # install deps (incl. dev group)
uv run pytest                        # run all tests (spins up a throwaway Postgres via testcontainers)
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

### Postgres-backed tests

Postgres is the sole persistence backend (ADR-024), so `uv run pytest` needs a running Docker
daemon — `tests/conftest.py`'s `postgres_config` fixture starts a throwaway container for the
whole test session automatically, no `docker compose up` required. Use the project venv's
pytest, not a system one (missing `fastapi`/`telegram`/`lmstudio` imports = wrong interpreter).

To run the **app** itself against a persistent local Postgres (rather than the ephemeral
per-test-run one):

```bash
scripts/db_services.sh up            # start postgres + pgAdmin (docker compose)
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
  LLM prompt (templates `{{char}}`/`{{user}}`/`{{world}}`, scenario rules, initial context,
  and the session's `SessionDirectives` sections — see `docs/DOMAIN_MODEL.md`).
- **`application/services/`** — use-case orchestration. `PlaythroughService` (`ScenarioDefinitionStore`
  → start/resume/restart a playthrough), `ChatService` (send/continue/retry a turn),
  `SessionDirectiveService` (language / scenario rules / director instruction), and
  `ScenarioTransferService` (import/export scenarios + sessions, see below) are the primary
  entry points the adapters call.
- **`adapters/`** — `telegram/` and `api/`. Transport concerns live here: slash-command
  parsing, **authorization/invocation policy**, message splitting. Adapters hold no business
  logic. Telegram is the fully-featured surface. Since **S031** the admin panel can also
  advance a story — send a turn, continue, retry — but browsing scenarios, starting one, and
  the directive commands (`/director`, `/rule`, `/language`, `/memory`) stay Telegram-only.
- **`infrastructure/`** — port implementations: `llm/lmstudio/`, `postgres/` (SQLAlchemy
  async + Alembic, the sole persistence backend), `scenario_transfer.py` (reads curated
  scenario JSON files for import), `config/settings.py` (pydantic-settings, `RP_ENGINE_`-prefixed
  env).
- **`app/main.py`** is the **composition root** — the only place that wires concrete
  Postgres implementations to ports.

### Domain model: scenario-centric

The engine is **scenario-native**: `User → ScenarioDefinition → ScenarioSession →
Conversation`. A `ScenarioDefinition` is an immutable blueprint (world, characters, rules,
opening); a `ScenarioSession` is a per-owner runtime instance. `Character` is an *optional*
embedded asset, not a root entity. There is **no v1 backward compatibility** — the old
character-centric `Session` model was fully removed (see `docs/adr/` ADR-023).

### Persistence: Postgres-only, JSON is import/export (ADR-024)

Postgres is the **sole runtime persistence backend** — there is no JSON store fallback.
`infrastructure/scenario_serialization.py` (domain ⇄ payload dict, both directions) backs both
the Postgres stores and `ScenarioTransferService`; **one contract-test suite** exercises each
store port (`tests/.../contracts/`, run against Postgres via the testcontainers fixture).
Changing storage semantics means updating the shared serializer and keeping the contract suite
green. PG schema changes require an Alembic migration that is **reversible** (verify
`upgrade head` *and* `downgrade` against a real DB).

Curated scenarios still ship as JSON files (`data/catalog/` by default,
`RP_ENGINE_SCENARIO_CATALOG_DIRS`) but are **imported into Postgres on every boot**
(`ScenarioTransferService.import_directory`, wired into `app/lifespan.py`) rather than being
read directly at runtime — `PlaythroughService` reads scenarios from `ScenarioDefinitionStore`
only. The admin panel (S010) is the only place scenarios/sessions are *authored/edited*;
JSON import/export is a transfer format, not a live source.

## Documentation map

Substantial design docs live in `docs/` — read the relevant one before large changes:

| Doc | For |
|---|---|
| `docs/ARCHITECTURE.md` | layer responsibilities, dependency rules, command flows |
| `docs/DOMAIN_MODEL.md` | domain entities and terminology |
| `docs/DATABASE_MODEL.md` | PostgreSQL tables ↔ repository mapping |
| `docs/adr/` | ADRs, one per file (ADR-023 = the scenario pivot, ADR-024 = Postgres-only persistence); index + front matter rules in `docs/adr/README.md` |
| `docs/SCENARIOS.md` | scenario authoring guide (JSON import/export + admin panel) |
| `docs/MEMORY.md` | the five memory layers — what each stores, returns and costs (ADR-026; design, not built) |
| `docs/ROADMAP.md` | milestones |

## Dev-loop tracking (`.devloop/`)

Tactical execution tracking, **committed to git** like `docs/`, but answering a different
question: `docs/` holds strategy and rationale, `.devloop/` holds what is in flight right now.

- `.devloop/BOARD.md` — kanban (VSCode "Markdown Kanban" extension), the glance view.
- `.devloop/epics/S###-<slug>.md` — one checklist per active epic. Each epic has a stable,
  incremental **story id** `S###` (assigned at creation, persists into the archive).
- `.devloop/archive/S###-YYYY-MM-DD-<slug>.md` — frozen, completed epics; **never edit**.

When starting/finishing a unit of work, follow `.devloop/README.md`: create/move the epic
file, take the next `S###`, and move its board card between columns. Next story number:
`ls .devloop/epics .devloop/archive | grep -oE 'S[0-9]+' | sort -u | tail -1`.
