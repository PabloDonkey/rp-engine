---
id: ADR-011
title: Conversation Model As Provider Boundary
status: accepted
created: 2026-07-12
supersedes: []
superseded_by: []
---

# ADR-011 — Conversation Model As Provider Boundary

## Context

The prior generation flow used a string-based prompt payload.

That flattened conversation structure and mixed domain semantics with provider formatting.

The roleplay engine requires a provider-independent, structured boundary that preserves message
roles and ordering.

## Decision

Adopt a structured domain conversation model as the generation boundary.

Core constructs:

* `ConversationRole` with domain roles `system`, `user`, `character`
* `ConversationMessage`
* `Conversation`
* `ConversationBuilder`

Provider interface update:

* before: `generate_response(prompt: PromptPayload)`
* after: `generate_response(conversation: Conversation)`

Role translation is provider adapter responsibility. The domain does not use provider-specific
roles such as `assistant`.

Structured history persistence for session conversations uses JSONL at:

* `data/sessions/<session_id>/history.jsonl`

## Rationale

* preserves conversation semantics across providers
* supports native chat APIs without prompt re-formatting in domain services
* keeps domain language aligned with roleplay concepts
* simplifies future provider additions and testing

## Consequences

### Positive

* Core no longer depends on prompt-string assembly.
* Provider adapters become explicit translation boundaries.
* History storage remains structured and append-friendly.

### Negative

* Requires coordinated refactor across service, orchestrator, provider, and tests.
* Existing string-prompt tests and assumptions must be updated.

### Disadvantages

* Requires maintaining an abstraction layer.
* Some provider-specific features may need additional interfaces.

---

## Rationale

The RP Engine is designed as a reusable roleplay engine, not an LM Studio application.

The language model backend is an implementation detail.

Keeping LM Studio inside infrastructure provides:

* local-first operation
* clean architecture boundaries
* easier testing
* future provider flexibility

The SDK reduces unnecessary integration code while preserving architectural independence.

---

## Consequences

### Positive

* Less custom API handling.
* Better alignment with LM Studio capabilities.
* Cleaner infrastructure implementation.
* Core engine remains provider-agnostic.
* Easier mocking during tests.

---

### Negative

* The SDK becomes an infrastructure dependency.
* Switching providers still requires a new provider implementation.
* LM Studio-specific features require careful abstraction decisions.

---

## Implementation Rules

The following rules apply:

1. `lmstudio` imports are only allowed inside:

```text
src/rp_engine/infrastructure/llm/
```

2. Core modules must only depend on an interface.

3. Tests should mock the provider interface, not the SDK.

4. Provider-specific features must not leak into domain models.

---

## Future Review

This decision should be revisited if:

* LM Studio SDK becomes unsuitable.
* Another provider becomes the primary target.
* Multi-provider support requires a different abstraction.

If replaced, create a new ADR that supersedes this decision rather than modifying this document.
