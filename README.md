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

## Install

```bash
uv sync
```

## Run

```bash
uv run uvicorn src.app.main:app --reload
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
