---
id: ADR-014
title: Transport Commands Belong to Adapters
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-014 — Transport Commands Belong to Adapters

## Context

RP Engine supports multiple transports such as Telegram and HTTP.

Transport command syntax (for example, Telegram `/continue`) is adapter-specific and should not leak into application or core layers.

When command parsing lives in application services, business logic becomes coupled to a transport and memory/LLM flows may accidentally persist transport syntax.

## Decision

Transport-specific syntax belongs to adapters.

The application layer exposes transport-agnostic use cases:

* `ChatService.send_message(...)`
* `ChatService.continue_story(...)`
* `ChatService.clear_conversation(...)`

Adapters translate transport actions into these use cases.

The core engine remains unaware of Telegram, HTTP, or slash commands.

## Alternatives Considered

### Option 1 — Parse transport commands in application services

### Advantages

* Fewer files in the short term.

### Disadvantages

* Couples application behavior to transport syntax.
* Increases risk of leaking commands into model prompts or memory.
* Makes additional adapters harder to add consistently.

---

### Option 2 — Adapter-owned command translation

Selected approach.

### Advantages

* Preserves application and core transport independence.
* Keeps adapters responsible for invocation policy and authorization.
* Ensures explicit, reusable application use cases.

### Disadvantages

* Requires small transport-focused modules per adapter.

## Rationale

RP Engine is domain-first and adapter-agnostic by design.

By localizing transport syntax in adapters and exposing explicit use-case methods in the application layer, architectural boundaries remain clear and reusable across Telegram, FastAPI, and future transports.

## Consequences

### Positive

* Clear adapter responsibilities.
* Reusable application API across transports.
* Reduced risk of command leakage into LLM prompts and persisted memory.
* Better isolated testing for parser, policy, and authorization.

### Negative

* Slight increase in adapter module count.
* More explicit wiring in composition root.

## Implementation Rules

1. Adapters own transport syntax parsing.
2. Adapters enforce transport invocation policy and authorization.
3. Application services expose transport-agnostic use-case methods.
4. Core engine must not parse or depend on transport commands.
5. FastAPI routes must map directly to application use cases with minimal business logic.
