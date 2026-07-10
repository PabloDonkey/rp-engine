# RP Engine - AI Context

## Project Overview

RP Engine is a local-first roleplay engine.

The goal is to create a reusable conversational engine that supports persistent roleplay, character consistency, world state, and long-term memory.

The engine must remain independent from communication platforms and language model providers.

Telegram is only an adapter, not the core application.

---

## Core Principles

* Local-first
* Provider-agnostic LLM integration
* Domain-first architecture
* Specification-driven development
* Strong typing
* Testability
* Minimal unnecessary complexity

---

## Architecture

The project follows a Ports and Adapters architecture.

High-level structure:

```
src/rp_engine/

app/
    Application startup and dependency composition

adapters/
    External interfaces
    Examples:
    - Telegram
    - REST API
    - CLI

core/
    Business logic

    domain/
        Entities and domain concepts

    engine/
        Roleplay orchestration

    services/
        Application workflows

    memory/
        Memory management logic

    prompts/
        Prompt construction

infrastructure/
    External implementations

    llm/
        LLM provider implementations

    storage/
        Persistence implementations

    config/
        Configuration handling
```

---

## Dependency Rules

Allowed:

```
adapters -> app -> core
infrastructure -> core interfaces
```

Forbidden:

```
core -> Telegram
core -> FastAPI
core -> LM Studio
core -> database
```

The domain must remain framework independent.

---

## Current Goal

Implement the first working vertical slice:

Telegram message
↓
Telegram Adapter
↓
Application Service
↓
RP Engine
↓
LM Studio Provider
↓
Telegram Response

Do not implement advanced memory, characters, or world simulation yet.
