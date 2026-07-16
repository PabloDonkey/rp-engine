# RP Engine

A local-first roleplay engine built around a clean domain architecture, long-term memory, and interchangeable LLM providers.

The project exposes its capabilities through adapters such as Telegram and a REST API while keeping the core engine independent of any specific interface or model provider.

## Goals

* Local-first by default
* Provider-agnostic LLM integration
* Long-term conversation memory
* Character and world state management
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
* Telegram bot adapter
* LM Studio provider
* Session management
* Conversation orchestration

## Planned

* Multiple LLM providers
* Character management
* World state tracking
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

PostgreSQL application variables (used when `RP_ENGINE_PERSISTENCE_BACKEND=postgres`):

* `RP_ENGINE_POSTGRES_HOST`
* `RP_ENGINE_POSTGRES_PORT`
* `RP_ENGINE_POSTGRES_DATABASE`
* `RP_ENGINE_POSTGRES_USER`
* `RP_ENGINE_POSTGRES_PASSWORD`
* `RP_ENGINE_POSTGRES_SSL_MODE` (`disable` or `require`)
* `RP_ENGINE_POSTGRES_POOL_SIZE`
* `RP_ENGINE_POSTGRES_MAX_OVERFLOW`

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
docker compose up -d
```

Stop services:

```bash
docker compose down
```

Reset database data (removes all postgres and pgAdmin persisted state):

```bash
docker compose down -v
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

## First Run Test

1. Start LM Studio.
2. Load a model that matches `RP_ENGINE_LMSTUDIO_MODEL`.
3. Set `RP_ENGINE_TELEGRAM_ENABLED=true` and configure `RP_ENGINE_TELEGRAM_BOT_TOKEN` in `.env`.
4. Start RP Engine.
5. Open Telegram and send a message to the bot.
6. Confirm a response is received.

## Telegram Commands

Registered Telegram menu commands:

* `/start` - Show welcome and usage information.
* `/chat <message>` - Send a message to the active character (recommended in groups).
* `/continue` - Continue the previous assistant reply.
* `/regenerate` - Replace only the latest assistant reply.
* `/clear` - Clear the current conversation.
* `/beta` - Request a closed-beta seat (stores one JSON request per Telegram user).

`/regenerate` behavior:

* After a normal user -> assistant turn, it regenerates from the latest user message.
* After `/continue`, it regenerates as a continuation from the previous assistant reply.
* Repeated `/regenerate` calls always replace only the latest assistant reply.

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

| Document          | Description                   |
| ----------------- | ----------------------------- |
| `VISION.md`       | Project goals and philosophy  |
| `SPEC.md`         | Functional requirements       |
| `DOMAIN.md`       | Domain model and terminology  |
| `ARCHITECTURE.md` | System architecture           |
| `API.md`          | HTTP API specification        |
| `DECISIONS.md`    | Architecture decision records |
| `ROADMAP.md`      | Planned milestones            |
| `TESTING.md`      | Testing strategy              |

---

# Status

This project is under active development. The architecture is being established first, followed by incremental implementation of the engine and adapters.

New features are expected to be implemented only after their specifications have been documented.
