---
id: ADR-019
title: Provider Owns Conversation Serialization
status: accepted
created: 2026-07-12
supersedes: []
superseded_by: []
---

# ADR-019 — Provider Owns Conversation Serialization

## Context

The engine now builds structured domain conversations and must remain provider-agnostic.

If application services or core components serialize provider payloads directly, provider-specific
roles and SDK concepts leak into domain and application layers.

## Decision

Provider adapters own translation from domain conversation models to provider SDK chat payloads.

The provider interface operates on provider-independent models:

* input: `Conversation`
* input: `GenerationSettings`
* output: `LLMResponse`

Provider adapters normalize completion semantics into `LLMResponse.finish_reason`, including
`length` for token-limit completions.

Provider adapters must convert provider exceptions into provider-independent errors:

* `LLMConnectionError`
* `LLMTimeoutError`
* `LLMGenerationError`

## Rationale

* Preserves clean architecture boundaries.
* Keeps domain language roleplay-first (`character`) instead of provider-first (`assistant`).
* Supports adding future providers without changing application services or core domain logic.
* Improves testability through provider-independent contracts.

## Consequences

### Positive

* SDK-specific chat/message types stay inside infrastructure.
* Core tests no longer need provider SDK imports.
* Completion behavior is explicit through normalized finish reasons.

### Negative

* Provider adapters require explicit mapper and error-conversion code.
* New providers must implement serialization and normalization logic.
