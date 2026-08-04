---
id: ADR-017
title: Transport Adapters Handle Message Size Limits
status: accepted
created: 2026-07-11
supersedes: []
superseded_by: []
---

# ADR-017 — Transport Adapters Handle Message Size Limits

## Context

Different transports impose different output size limits. Telegram, for example, rejects oversized
messages. These constraints vary by platform and may change independently from core business logic.

If message-size handling is implemented in application services or core business logic, platform
knowledge leaks into transport-agnostic layers.

## Decision

Platform-specific output size limits are handled in adapters.

The core engine always produces one complete response string.

Adapters are responsible for delivery behavior such as splitting long responses into multiple
platform-compliant messages.

## Rationale

Message-size limits are transport constraints, not domain rules.

Keeping delivery adaptation inside adapters preserves boundary rules and allows each transport to
apply its own strategy without changing core components.

## Consequences

### Positive

* Core stays platform-agnostic.
* Adapter behavior is easier to test with transport-specific edge cases.
* New transports can define independent delivery policies.

### Negative

* Adapter modules gain additional delivery logic.
