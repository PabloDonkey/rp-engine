---
id: ADR-010
title: Use LM Studio Python SDK
status: accepted
created: 2026-07-10
supersedes: []
superseded_by: []
---

# ADR-010 — Use LM Studio Python SDK

## Context

RP Engine requires a language model provider integration.

The first implementation target is LM Studio because it provides local model hosting and an OpenAI-compatible ecosystem for running local LLMs.

The project must avoid coupling the core engine to a specific LLM provider.

The integration approach must balance:

* simplicity
* maintainability
* future provider replacement
* access to LM Studio features

---

## Decision

Use the official LM Studio Python SDK as the initial LM Studio integration.

The SDK implementation will live exclusively in the infrastructure layer.

The core engine will communicate through an abstract LLM provider interface.

Architecture:

```text
core
 |
 | depends on abstraction
 v

LLMProvider interface

        ^
        |
        |

infrastructure

        |
        v

LM Studio Python SDK
```

The RP Engine core must never import or depend on the `lmstudio` package.

---

## Alternatives Considered

### Option 1 — Direct OpenAI-compatible HTTP API

Use LM Studio's OpenAI-compatible REST endpoint through an HTTP client.

Example:

```text
core
 |
LLM interface
 |
LM Studio HTTP client
 |
LM Studio API
```

### Advantages

* Uses a common API format.
* Easy provider replacement.
* Similar to OpenAI-compatible services.

### Disadvantages

* Requires maintaining HTTP integration code.
* Does not expose LM Studio-specific capabilities directly.

---

### Option 2 — Direct LM Studio SDK Usage Everywhere

Use the SDK throughout the application.

### Advantages

* Simple initial implementation.
* Full access to LM Studio features.

### Disadvantages

* Creates provider coupling.
* Makes future provider changes difficult.
* Violates architecture boundaries.

---

### Option 3 — LM Studio SDK Behind Provider Abstraction

Selected approach.

### Advantages

* Simple implementation.
* Keeps core independent.
* Allows future providers.
* Provides access to LM Studio features.
