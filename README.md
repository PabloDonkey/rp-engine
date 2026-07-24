# RP Engine

A local-first, scenario-driven interactive-fiction engine built around a clean domain architecture, long-term memory, and interchangeable LLM providers.

Players pick from a developer-curated library of scenarios (reusable blueprints of a world, characters, rules, and an opening) and play them as adventures. The project exposes its capabilities through adapters such as Telegram and a REST API while keeping the core engine independent of any specific interface or model provider.

## Goals

* Local-first by default
* Provider-agnostic LLM integration
* Long-term conversation memory
* Scenario-driven continuity (world + characters + rules as reusable blueprints)
* Spec-driven development
* Modular, testable architecture
* Async-first implementation

## Non-Goals

* Tightly coupling the engine to a single chat platform
* Vendor-specific LLM APIs
* Business logic inside adapters
* UI-specific assumptions inside the engine

---

# Features

## Current

* FastAPI application
* Telegram bot adapter (scenario-driven command surface)
* LM Studio provider
* Curated scenario library (JSON catalog) and playthrough management
* Conversation orchestration with truncation-aware `/continue` and in-place `/retry`
* Dual persistence backends (JSON and PostgreSQL)

## Planned

* Multiple LLM providers
* Story-graph progression and world-state mechanics
* Memory summarization
* Tool calling
* Image generation
* Multiple chat adapters (Discord, Matrix, Web, CLI)

---

# Technology Stack

| Component       | Technology                    |
| --------------- | ----------------------------- |
| Language        | Python                        |
| Package Manager | uv                            |
| Web Framework   | FastAPI                       |
| ASGI Server     | Uvicorn                       |
| Telegram        | python-telegram-bot           |
| Validation      | Pydantic v2                   |
| LLM             | LM Studio (OpenAI-compatible) |
| Linting         | Ruff                          |
| Type Checking   | mypy                          |
| Testing         | pytest                        |

---

# Project Structure

```text
src/
├── adapters/
│   ├── telegram/
│   └── api/
│
├── app/
│
├── domain/
│
├── engine/
│
├── llm/
│
├── memory/
│
├── services/
│
├── infrastructure/
│
└── config/

tests/

docs/
```

---

# Development

## Installation

```bash
uv sync
```

## Environment setup

```bash
cp .env.example .env
```

Edit `.env` and set at least these required values:

* `RP_ENGINE_TELEGRAM_ENABLED` (`true` to run with Telegram, `false` for local/dev without Telegram)
* `RP_ENGINE_TELEGRAM_BOT_TOKEN` (required when Telegram is enabled)
* `RP_ENGINE_TELEGRAM_ADMIN_USER_ID` (Telegram numeric user ID allowed to run hidden admin commands)
* `RP_ENGINE_LMSTUDIO_API_HOST` (LM Studio API host in `host:port` format)
* `RP_ENGINE_LMSTUDIO_MODEL` (loaded model identifier)

Optional application variables:

* `RP_ENGINE_APP_ENVIRONMENT` (`development`, `test`, or `production`)
* `RP_ENGINE_LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
* `RP_ENGINE_APP_HOST`
* `RP_ENGINE_APP_PORT`
* `RP_ENGINE_DEBUG_STATUS_ENABLED`
* `RP_ENGINE_DEBUG_GENERATION_TRACE` (`off`, `errors`, or `all`; default `off`)
* `RP_ENGINE_PERSISTENCE_BACKEND` (`json` or `postgres`; default `json`)
* `RP_ENGINE_SCENARIO_CATALOG_DIRS` (comma-delimited list of scenario catalog directories,
  merged in load order with later directories winning on id collisions; default `data/catalog`)

PostgreSQL application variables (used when `RP_ENGINE_PERSISTENCE_BACKEND=postgres`):

* `RP_ENGINE_POSTGRES_HOST`
* `RP_ENGINE_POSTGRES_PORT`
* `RP_ENGINE_POSTGRES_DATABASE`
* `RP_ENGINE_POSTGRES_USER`
* `RP_ENGINE_POSTGRES_PASSWORD`
* `RP_ENGINE_POSTGRES_SSL_MODE` (`disable` or `require`)
* `RP_ENGINE_POSTGRES_POOL_SIZE`
* `RP_ENGINE_POSTGRES_MAX_OVERFLOW`
* `RP_ENGINE_POSTGRES_STARTUP_CHECK_FAIL_FAST` (default `true`; abort startup if Postgres is
  unreachable — set `false` to log and continue instead, with `/health` reporting `db: unavailable`)

Generation trace behavior:

* `off`: no generation traces are written
* `errors`: write traces only when generation fails
* `all`: write traces for every completed generation

When enabled, traces are stored as JSON Lines at:

* `data/sessions/<session_id>/trace.jsonl`

## Run application

```bash
uv run python -m uvicorn --app-dir src rp_engine.app.main:app --host 0.0.0.0 --port 8000
```

For local development with code reload:

```bash
uv run python -m uvicorn --app-dir src rp_engine.app.main:app --reload --host 0.0.0.0 --port 8000
```

## Local PostgreSQL Stack (Docker)

Start PostgreSQL + pgAdmin:

```bash
scripts/db_services.sh up
```

If your Docker CLI does not include the `compose` subcommand, use:

```bash
docker-compose up -d
```

or use the repository helper that auto-detects both variants:

```bash
scripts/compose.sh up -d
```

If you get `permission denied while trying to connect to the docker API`, add your user to the `docker` group and re-login:

```bash
sudo usermod -aG docker "$USER"
# then log out and log in again
```

If you want to update Docker to use the modern Compose plugin (`docker compose`), install:

```bash
sudo apt update
sudo apt install docker-compose-v2
```

Stop services:

```bash
scripts/db_services.sh down
```

Reset database data (removes all postgres and pgAdmin persisted state):

```bash
scripts/db_services.sh reset
```

Persistent data is stored in Docker named volumes:

* `postgres_data`
* `pgadmin_data`

pgAdmin is available at:

* `http://localhost:5050`

Run DB migrations:

```bash
uv run alembic upgrade head
```

Connect with psql:

```bash
psql postgresql://rp_engine:change_me@localhost:5432/rp_engine
```

## Lint

```bash
uv run ruff check .
```

## Format

```bash
uv run ruff format .
```

## Type Check

```bash
uv run mypy .
```

## Test

```bash
uv run pytest
```

## PostgreSQL Tests

Launch local database services first:

```bash
scripts/db_services.sh up
```

Fallback when `docker compose` is unavailable:

```bash
docker-compose up -d
```

Recommended one-shot command (starts DB services and runs tests in project environment):

```bash
scripts/test_postgres.sh
```

Run all tests with PostgreSQL integration tests enabled:

```bash
RP_ENGINE_RUN_POSTGRES_TESTS=1 /home/pablo/projects/rp-engine/.venv/bin/python -m pytest
```

Run only the PostgreSQL store contract tests (character + scenario):

```bash
RP_ENGINE_RUN_POSTGRES_TESTS=1 /home/pablo/projects/rp-engine/.venv/bin/python -m pytest tests/integration/infrastructure/
```

If you see import errors like missing `fastapi`, `telegram`, or `lmstudio`, you are likely using a system `pytest` instead of the project virtual environment. Use one of these options:

```bash
source .venv/bin/activate
RP_ENGINE_RUN_POSTGRES_TESTS=1 pytest
```

or

```bash
RP_ENGINE_RUN_POSTGRES_TESTS=1 /home/pablo/projects/rp-engine/.venv/bin/python -m pytest
```

## First Run Test

1. Start LM Studio.
2. Load a model that matches `RP_ENGINE_LMSTUDIO_MODEL`.
3. Set `RP_ENGINE_TELEGRAM_ENABLED=true` and configure `RP_ENGINE_TELEGRAM_BOT_TOKEN` in `.env`.
4. Start RP Engine.
5. Open Telegram and send a message to the bot.
6. Confirm a response is received.

## Telegram Commands

RP Engine plays like an interactive-fiction adventure: players pick a scenario from a
curated library and play through plain chat messages. Commands are only for game/session
management.

Registered Telegram menu commands (authorized players):

* `/start` - State-aware entry point. If you have an adventure in progress it auto-resumes
  it (like reopening a saved game); otherwise it points you at `/scenarios`.
* `/scenarios` - Browse the curated library of available adventures.
* `/play <id>` - Start (or replace) a playthrough of the chosen scenario.
* `/continue` - Let the story advance with no input. If the previous narrator reply was
  cut off at the model's token limit, `/continue` instead resumes that truncated reply.
* `/retry` - Regenerate the most recent narrator reply. In Telegram, the previous narrator
  message is deleted and replaced in place, so the story stays a single evolving thread.
* `/restart` - Delete the current playthrough and restart the scenario from the beginning.
* `/cancel` - Cancel the current menu/scripted interaction.
* `/help` - Show the commands available at your access level.
* `/beta` - Request a closed-beta seat (stores one JSON request per Telegram user).

Unauthorized users only see `/start`, `/help`, and `/beta`.

Playing the story:

* In **private chats**, plain messages are the primary way to play — just type what you do.
* In **group chats**, address the story explicitly with `/chat <message>`; plain group
  chatter is ignored so the bot does not respond to every message.
* In group chats, story/session-control commands (`/play`, `/restart`, `/continue`,
  `/retry`) are restricted to chat administrators and creators.

Scenarios are authored as JSON files in one or more catalog directories
(`RP_ENGINE_SCENARIO_CATALOG_DIRS`, default `data/catalog/`). See `docs/SCENARIOS.md` for
the authoring guide.

## Telegram Admin Commands (Hidden)

These commands are intentionally hidden from Telegram command menu registration and are for administrators only.

* `/admin_beta_list` - List pending beta requests in chronological order.
* `/admin_beta_accept <telegram_id|list_index>` - Approve a pending request, add user to authorization, and remove request.
* `/admin_beta_reject <telegram_id|list_index> [reason]` - Reject a pending request and archive it under `data/telegram/beta_rejected/`.

Only the user configured in `RP_ENGINE_TELEGRAM_ADMIN_USER_ID` can execute these commands.

---

# Design Principles

* KISS
* SOLID
* DRY
* YAGNI
* Domain-first design
* Dependency inversion
* Async-first
* Strong typing
* Testability

---

# Architecture

The project follows a layered architecture.

```
Adapters
      │
Application
      │
Services
      │
Engine
      │
Domain
      │
Infrastructure
```

External systems (Telegram, REST, CLI, Discord, etc.) communicate with the application through adapters. The core engine contains no platform-specific code.

---

# Documentation

Additional project documentation can be found in the `docs/` directory.

Character cards use Character Card Specification v3 as the portable external definition format,
mapped into RP Engine's internal character domain model.

| Document          | Description                   |
| ----------------- | ----------------------------- |
| `VISION.md`       | Project goals and philosophy  |
| `SPEC.md`         | Functional requirements       |
| `SPEC_V3.md`      | Character Card v3 specification |
| `SCENARIOS.md`    | Scenario authoring guide (JSON catalog) |
| `DOMAIN_MODEL.md` | Domain model and terminology  |
| `DATABASE_MODEL.md` | PostgreSQL persistence mapping |
| `ARCHITECTURE.md` | System architecture           |
| `API.md`          | HTTP API specification        |
| `DECISIONS.md`    | Architecture decision records |
| `ROADMAP.md`      | Planned milestones            |
| `TESTING.md`      | Testing strategy              |

---

# Status

This project is under active development. The architecture is being established first, followed by incremental implementation of the engine and adapters.

New features are expected to be implemented only after their specifications have been documented.
