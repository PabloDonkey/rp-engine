# Vision

## Purpose

RP Engine is a local-first conversational engine designed for immersive, persistent roleplay experiences.

The project separates roleplay logic from user interfaces and language model providers, allowing the same engine to power Telegram, web applications, desktop clients, or future platforms without changing the core domain.

The primary goal is to create a maintainable, extensible system that preserves long-term narrative consistency while remaining simple to understand and evolve.

---

# Philosophy

The project is guided by a few core principles.

## Local First

Users should own their data.

The engine should work entirely on local hardware whenever possible. Cloud services are optional, not required.

---

## Domain First

The roleplay engine is the product.

Telegram, Discord, REST APIs, web interfaces, and other integrations are simply adapters that communicate with the engine.

Business rules should never depend on a specific platform.

---

## Provider Agnostic

Language models are interchangeable.

The engine should communicate through an abstraction rather than depending on a single implementation.

Supported providers may include:

* LM Studio
* Ollama
* llama.cpp
* OpenAI-compatible APIs
* Future providers

Changing providers should require configuration, not architectural changes.

---

## Long-Term Memory

Conversations are persistent.

The engine should preserve important information over time through summarization, structured state, and memory retrieval rather than relying solely on the language model's context window.

---

## Specification Driven

Behavior is designed before implementation.

Requirements should be documented before code is written.

Architecture should emerge from the specification rather than the implementation.

---

## Simplicity

Complexity should be introduced only when it solves a demonstrated problem.

The project favors:

* KISS
* YAGNI
* SOLID
* DRY

Simple, understandable code is preferred over clever abstractions.

---

## Testability

Every important component should be independently testable.

Core business logic should be executable without Telegram, FastAPI, or a running language model.

---

# Vision

The long-term vision is to build a reusable conversational engine capable of supporting:

* Persistent roleplay
* Character simulation
* World simulation
* Narrative memory
* Tool use
* Multiple communication platforms
* Multiple language model providers

The engine should become a foundation that can be reused across many applications rather than a solution built for a single interface.

---

# Success Criteria

The project is successful when:

* The core engine has no dependency on Telegram or any other client.
* Multiple LLM providers can be swapped through configuration.
* Conversations remain coherent across long sessions.
* Character personalities remain consistent over time.
* World state persists independently of the language model.
* New adapters can be added without modifying the domain.
* The codebase remains understandable to contributors after years of development.

---

# Non-Goals

The project does not aim to:

* Become tied to a single messaging platform.
* Depend on proprietary AI services.
* Maximize the number of features at the expense of maintainability.
* Replace game engines or visual novel frameworks.
* Build a general-purpose chatbot unrelated to persistent roleplay.

---

# Guiding Principle

Every architectural decision should move the project toward a reusable, platform-independent roleplay engine with clear boundaries, long-term maintainability, and user ownership of data.
