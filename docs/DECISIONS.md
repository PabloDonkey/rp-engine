# Architecture Decisions

This document records significant architectural decisions made during the development of RP Engine.

Each decision captures the context, alternatives considered, rationale, and consequences.

The goal is to preserve the reasoning behind important choices, not simply record what changed.

---

# ADR-001 — Local-First Architecture

**Status:** Accepted

## Context

Users should be able to operate the engine without relying on cloud services.

## Decision

The engine is designed to operate entirely on local hardware whenever possible.

Cloud-hosted services are optional.

## Rationale

* User ownership of data
* Privacy
* Offline operation
* Lower operating cost

## Consequences

### Positive

* Conversations remain private.
* No recurring API costs.
* Works without Internet access.

### Negative

* Local hardware requirements.
* Performance depends on the user's machine.

---

# ADR-002 — Provider Abstraction

**Status:** Accepted

## Context

The project should not depend on a single LLM implementation.

## Decision

The engine communicates through a provider interface rather than directly with a specific API.

## Alternatives

* Direct LM Studio integration
* OpenAI SDK
* Provider abstraction

## Rationale

A provider abstraction allows new model backends to be added without changing business logic.

## Consequences

### Positive

* Easy provider replacement.
* Better testing.
* Reduced vendor lock-in.

### Negative

* Slightly more abstraction.

---

# ADR-003 — Platform Independence

**Status:** Accepted

## Context

The engine should support multiple communication platforms.

## Decision

Telegram, REST, CLI, and future interfaces are implemented as adapters.

## Rationale

The roleplay engine is the product.

Communication platforms are simply ways to interact with it.

## Consequences

### Positive

* Easier expansion.
* Better separation of concerns.

### Negative

* Slightly more project structure.

---

# ADR-004 — Layered Architecture

**Status:** Accepted

## Context

Business rules should remain isolated from external frameworks.

## Decision

The project adopts a layered architecture inspired by Ports & Adapters.

## Rationale

This keeps business logic independent from FastAPI, Telegram, and infrastructure concerns.

## Consequences

### Positive

* Easier testing.
* Cleaner dependencies.
* Better maintainability.

### Negative

* More interfaces.

---

# ADR-005 — Async-First Design

**Status:** Accepted

## Context

The application handles network requests and external providers.

## Decision

The project uses asynchronous APIs by default.

## Rationale

Asynchronous execution improves scalability and resource utilization.

## Consequences

### Positive

* Better concurrency.
* Efficient I/O.

### Negative

* Increased implementation complexity.

---

# ADR-006 — Modern Python Tooling

**Status:** Accepted

## Context

The project requires consistent development tooling.

## Decision

The standard development tools are:

* uv
* Ruff
* mypy
* pytest

## Rationale

These tools provide a fast, modern, and consistent development experience.

## Consequences

### Positive

* Fast dependency management.
* Consistent formatting.
* Static analysis.
* Automated testing.

### Negative

* Contributors must learn the toolchain.

---

# ADR-007 — Specification-Driven Development

**Status:** Accepted

## Context

Implementation should follow documented requirements rather than ad hoc feature development.

## Decision

Functional requirements are documented before implementation.

Architecture evolves from the specification.

## Rationale

A specification-first workflow improves clarity, planning, and maintainability.

## Consequences

### Positive

* Clear project direction.
* Easier reviews.
* Better traceability.
* Improved documentation.

### Negative

* Higher upfront documentation effort.

---

# ADR-008 — Strong Typing

**Status:** Accepted

## Context

The project is expected to grow in size and complexity.

## Decision

The codebase uses static typing throughout.

Type checking is enforced with mypy.

## Rationale

Strong typing improves maintainability, refactoring, and tooling support.

## Consequences

### Positive

* Earlier error detection.
* Better IDE support.
* Safer refactoring.

### Negative

* Additional type annotations.

---

# ADR-009 — Configuration Outside Code

**Status:** Accepted

## Context

Runtime behavior should not require code modifications.

## Decision

Configuration is externalized through configuration files and environment variables.

## Rationale

Separating configuration from implementation simplifies deployment and testing.

## Consequences

### Positive

* Flexible deployments.
* Cleaner code.

### Negative

* Additional configuration management.

---

# ADR-010 — Use LM Studio Python SDK

**Status:** Accepted

**Date:** 2026-07-10

---

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

---

# ADR-011 — Conversation Model As Provider Boundary

**Status:** Accepted

**Date:** 2026-07-12

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


---

# ADR-012 — Application Composition Root

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

RP Engine uses adapters, application services, core business logic, and infrastructure implementations that must remain loosely coupled.

Dependency creation and runtime lifecycle ownership must be consistent across adapters, especially for Telegram polling startup and shutdown.

If adapters create services or infrastructure directly, architectural boundaries erode and testing becomes harder.

## Decision

The application layer is the composition root.

The application layer owns:

* configuration resolution
* dependency creation
* dependency wiring
* runtime lifecycle start/stop

Adapters only translate transport input/output and delegate to application services.

For Telegram specifically:

* application lifespan starts and stops Telegram runtime
* Telegram adapter does not construct services
* Telegram adapter does not initialize infrastructure

## Alternatives Considered

### Option 1 — Adapter-owned wiring

Allow each adapter to create its own service graph.

### Advantages

* Less initial setup in the app layer.

### Disadvantages

* Boundary violations.
* Duplicate wiring logic.
* Harder lifecycle coordination.
* Reduced testability.

---

### Option 2 — Distributed composition by module

Split dependency wiring across adapters and infrastructure modules.

### Advantages

* Smaller local setup functions.

### Disadvantages

* Hidden dependency graph.
* Ambiguous ownership of startup/shutdown.
* Higher maintenance overhead.

---

### Option 3 — Application-owned composition root

Selected approach.

### Advantages

* Clear ownership.
* Explicit dependency graph.
* Clean adapter boundaries.
* Easier integration testing.

### Disadvantages

* Slightly more up-front wiring code in the app layer.

## Rationale

RP Engine is intended to stay framework-agnostic in core business logic while supporting multiple adapters and providers.

A single composition root in the application layer enforces consistent boundaries and keeps lifecycle orchestration centralized.

This aligns with the project's dependency direction and keeps adapters thin.

## Consequences

### Positive

* Better architecture clarity.
* Predictable startup/shutdown behavior.
* Reduced coupling in adapters.
* Easier end-to-end internal flow tests.

### Negative

* Application wiring module grows as integrations increase.
* Requires discipline to avoid backsliding into adapter-owned setup.

## Implementation Rules

1. Build dependencies in the application layer.
2. Pass concrete implementations to core abstractions through constructors.
3. Keep adapters free from dependency graph construction.
4. Start and stop external runtimes from the application lifespan.


---

# ADR-013 — Separate Conversation Storage and Memory Strategy

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

Milestone 2 introduces persistent conversation memory.

Without explicit boundaries, the implementation can collapse storage, context selection, summarization, and retrieval into one component. That would make future evolution toward sliding windows, summaries, and retrieval strategies harder.

RP Engine needs interchangeable storage implementations and interchangeable context-building strategies.

## Decision

Treat memory as two independent concerns:

1. Conversation Storage
2. Memory Strategy

Conversation storage is responsible only for persistence operations such as:

* `save_message()`
* `load_messages()`
* `clear()`

Memory strategy is responsible only for converting stored conversation history into model context.

Dependency direction:

```text
core

        ports/
                conversation_store.py
                memory_strategy.py


infrastructure/

        storage/
                json_conversation_store.py
```

For Milestone 2, implement:

* `JsonConversationStore`
* `DumpEverythingStrategy`

`DumpEverythingStrategy` returns all available stored messages as context.

Do not implement summarization, retrieval, embeddings, or hybrid memory logic in this milestone.

## Alternatives Considered

### Option 1 — Single memory manager owning all concerns

One component stores messages, chooses context, summarizes, and retrieves.

### Advantages

* Faster initial implementation.
* Fewer files and interfaces.

### Disadvantages

* Tight coupling across unrelated responsibilities.
* Harder to replace storage without touching context logic.
* Harder to introduce new strategies incrementally.

---

### Option 2 — Separate storage and strategy concerns

Selected approach.

### Advantages

* Clear responsibilities.
* Independent replaceability of persistence and context logic.
* Better testability per concern.
* Safer path for future advanced memory strategies.

### Disadvantages

* Slightly more abstraction in Milestone 2.

## Rationale

RP Engine is designed for incremental evolution.

Separating storage from strategy keeps Milestone 2 simple while preserving compatibility with future context policies.

This avoids premature coupling and keeps architectural options open for later milestones.

## Consequences

### Positive

* Core owns stable contracts for both concerns.
* Infrastructure can add new store backends independently.
* Memory strategies can evolve without changing persistence code.
* Prompt assembly receives explicit context output from strategy logic.

### Negative

* More interfaces to maintain.
* Additional wiring in the composition root.

## Implementation Rules

1. Do not create a generic memory manager that combines storage and strategy.
2. Keep persistence decisions out of memory strategy implementations.
3. Keep context selection decisions out of storage implementations.
4. Route chat flow through store load, strategy build, prompt build, LLM call, then store save.
5. Milestone 2 strategy must be `DumpEverythingStrategy` only.


---

# ADR-014 — Transport Commands Belong to Adapters

**Status:** Accepted

**Date:** 2026-07-10

---

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


---

# ADR-015 — Group Authorization Uses Conversation Identity

**Status:** Superseded

**Date:** 2026-07-10

---

## Context

Milestone 2B introduces Telegram group support with independent authorization behavior.

Private chats and group chats have different trust boundaries:

* private chats are controlled by user-level allowlists
* group chats are controlled by group-level allowlists

If group access is decided per user in group chats, adapter behavior becomes inconsistent and harder to reason about.

## Decision

For Telegram group conversations, authorization is performed at the group identity level.

Rules:

* private chat authorization checks `user_id`
* group chat authorization checks `group_id`
* users in authorized groups inherit access from the group authorization state

Conversation identity resolution remains adapter-owned.

## Rationale

Group chats are shared conversation spaces.

Authorizing by group identity aligns access control with the same identity used for memory isolation and keeps the core layer transport-agnostic.

## Consequences

### Positive

* Consistent policy for all members in an authorized group.
* Cleaner adapter logic for group conversations.
* Clear mapping between authorization boundary and adapter-level group identity.

### Negative

* Group-level authorization grants access to all members, not selected individuals.


---

# ADR-016 — Store User Metadata Separately From Message Content

**Status:** Accepted

**Date:** 2026-07-10

---

## Context

Group conversations require multi-user attribution for prompt construction.

Injecting names directly into stored text couples storage format to prompt rendering style and makes future formatting changes brittle.

## Decision

Conversation messages store speaker metadata in separate fields from text content.

Stored user messages may include:

* `user_id`
* `username`
* `display_name`
* `content`

Prompt rendering decides how to represent speaker attribution at generation time.

## Rationale

Separating identity data from content preserves clean memory records and allows multiple rendering strategies without rewriting history.

## Consequences

### Positive

* Message content remains clean and reusable.
* Prompt formatting can evolve independently.
* Better support for group and private prompt styles.

### Negative

* Storage and model types include additional optional fields.


---

# ADR-017 — Transport Adapters Handle Message Size Limits

**Status:** Accepted

**Date:** 2026-07-11

---

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


---

# ADR-018 — Internal User Identity

**Status:** Accepted

**Date:** 2026-07-11

---

## Context

External identifiers from adapters (for example Telegram user IDs) were being used directly to
identify users in engine-facing flows and conversation storage keys.

This coupling makes the core model transport-aware and complicates multi-adapter reuse.

## Decision

The engine uses internal collision-resistant UUIDs as primary user identifiers.

External platform identifiers are stored only as linked identities and resolved by adapters through
an identity resolution service before calling application use cases.

## Rationale

Internal IDs preserve domain ownership of identity and keep core logic independent from transport
platforms.

## Consequences

### Positive

* Core user model is provider-agnostic.
* Adapters can map identities without changing core business logic.
* Future transports can reuse the same user model.

### Negative

* Additional resolver and identity persistence components are required.


---

# Future Decisions

Future ADRs should follow this template.

```markdown
# ADR-XXX — Title

**Status:** Proposed | Accepted | Superseded | Rejected

## Context

What problem is being solved?

## Decision

What was decided?

## Alternatives

What other options were considered?

## Rationale

Why was this option selected?

## Consequences

### Positive

...

### Negative

...
```

Each ADR should describe a single architectural decision.

If a decision changes in the future, create a new ADR that supersedes the previous one rather than rewriting history.

---

# ADR-019 — Provider Owns Conversation Serialization

**Status:** Accepted

**Date:** 2026-07-12

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


---

# ADR-020 — Conversation Ownership and Identity Scope

**Status:** Accepted

**Date:** 2026-07-12

## Context

Previous iterations mixed transport identity (Telegram user/chat IDs) with roleplay ownership and
conversation state boundaries.

That created model drift between documentation and runtime behavior and made adapter expansion riskier.

## Decision

Adopt session ownership as the canonical identity scope:

* A `Conversation` belongs to a `Session`.
* A `Session` is owned by one domain owner context:
        * `user` owner
        * `group` owner
* Adapters map external identities into domain identities before session lookup/creation.

Core/domain/application layers reason about `User`, `Group`, `Session`, and `Conversation`.

Core/domain/application layers do not reason about Telegram-specific identifiers.

## Rationale

* Keeps ownership and memory boundaries inside the domain model.
* Prevents adapter/platform identifiers from leaking into core business rules.
* Supports future adapters (Discord, web, CLI) without domain changes.
* Enables separate roleplay contexts for the same owner by session.

## Consequences

### Positive

* Private flows resolve to user-owned sessions.
* Group flows resolve to group-owned sessions.
* Session memory and conversation history are consistently session-scoped.
* Group and user isolation rules are explicit and testable.

### Negative

* Additional identity mapping and persistence components are required.
* Existing session-store indices and tests must support owner-scoped keys.

## Supersedes

* ADR-015 (Group Authorization Uses Conversation Identity) is superseded where it tied
        conversation storage identity directly to transport private/group identity.


---

# ADR-021 — Remove Character State as a Domain Concept

**Status:** Accepted

**Date:** 2026-07-17

## Context

Initial architecture language described a dedicated structured Character State model for
relationship, emotion, inventory, and other runtime variables.

An implementation audit showed the current engine runtime does not consume a structured
Character State entity in generation or conversation workflows.

Current continuity is produced from:

* Character Definition (character card)
* Conversation Memory
* World Lore

The historical compatibility artifact (`state.json` written during JSON character creation)
was removed after confirming no runtime dependency.

## Decision

Remove Character State as an active domain concept.

The primary active runtime model is:

* Session
* Conversation
* Character Definition
* Memory
* Lore

Character evolution is represented through memory and conversation history.

Structured runtime state may be introduced in the future only when a concrete deterministic
feature requires it (for example inventory mechanics, health systems, quest flags, or
simulation variables), under a new ADR with focused scope.

## Rationale

* Align architecture with actual implementation behavior.
* Reduce conceptual and documentation drift.
* Keep persistence model simpler during current milestones.
* Follow a memory-first conversational architecture.

## Consequences

### Positive

* Simpler domain model and documentation.
* Clearer boundaries between character definition and session memory.
* Fewer speculative persistence concepts.
* Lower migration risk while PostgreSQL adoption is incremental.

### Negative

* Structured gameplay-style mechanics are out of current scope.
* Future deterministic features require a focused model-introduction ADR.

## Implementation Notes

* Removed legacy JSON `state.json` write path from character creation.
* Updated tests to assert character card persistence only.
* PostgreSQL schema remains unchanged because no Character State table exists.


---

# ADR-022 — Adopt Character Card Specification v3

**Status:** Accepted

**Date:** 2026-07-17

## Context

RP Engine requires a portable character definition format for import, export, and ecosystem
compatibility.

Maintaining a custom character card schema would duplicate existing community standards,
increase maintenance burden, and reduce interoperability.

## Decision

Adopt Character Card Specification v3 as the external character definition contract.

Canonical source:

* `docs/SPEC_V3.md`

The Character Card represents portable character definition concerns such as:

* identity (name and descriptive metadata)
* personality
* scenario
* behavior-guiding fields
* initial greeting (`first_mes`)

Engine-specific information remains outside the card:

* `owner_id`
* `visibility`
* database identifiers
* memories
* sessions
* runtime metadata

RP Engine maps Character Card v3 into its internal `Character` domain model through
application/domain mapping and validation layers.

## Consequences

### Positive

* Better compatibility with existing character-card ecosystems.
* Simpler import/export interoperability.
* Less custom schema maintenance in RP Engine.

### Negative

* Internal model requires explicit mapping from external card fields.
* Future Character Card spec versions require compatibility and migration handling.


---

# ADR-023 — Scenario-Centric Architecture

**Status:** Accepted

**Date:** 2026-07-22

## Context

RP Engine began as a character-centric roleplay bot: a user selected a `Character`, a
`Session` bound `owner + character + world`, and conversation flowed from there. The
product evolved into a scenario-based interactive-fiction engine, where the reusable unit
is a whole adventure (world + characters + rules + opening), not a single character.

The character-centric model made `Character` the root entity and coupled session identity
to a specific character. That did not support curated adventures, characterless/freeform
scenarios, or multi-character casts.

## Decision

Make the scenario the primary concept.

* `ScenarioDefinition` — a reusable, immutable blueprint: world, role profiles, characters
  (optional), rules, optional story graph, initial context.
* `ScenarioSession` — a runtime instance owned by a `user` or `group`: references a
  definition and holds all evolving state (active participants, world state, story
  progress, conversation history).
* `Character` becomes an optional asset used *within* a scenario, not the root entity.

The runtime is fully scenario-native end-to-end (Telegram adapter → `PlaythroughService`
/ `ChatService` → `ConversationBuilder`). Curated scenarios are authored as JSON in a
catalog directory (see `docs/SCENARIOS.md`) and selected with `/play`. User-facing
character creation/selection is removed from the product.

**Backward compatibility is explicitly not maintained** (the project is in beta):
pre-migration `Session` data may need to be recreated. Code was rewritten directly onto
scenario entities rather than keeping parallel legacy paths.

Both persistence backends (JSON and PostgreSQL) implement the scenario stores behind one
shared serializer and one behavioral contract suite.

## Alternatives

* Keep `Character` as the root and bolt scenarios on top — rejected: perpetuates the
  coupling this ADR removes.
* Maintain a v1 (character) and v2 (scenario) runtime side by side — rejected: doubles
  surface area for a pre-release product; the no-compat decision makes it unnecessary.

## Rationale

* Matches the product: players launch adventures, not chatbots.
* Cleanly separates immutable blueprint (`ScenarioDefinition`) from runtime state
  (`ScenarioSession`).
* Supports characterless/freeform scenarios and future multi-character casts.
* Curated JSON catalog lets developers author content without code changes.

## Consequences

### Positive

* Clean domain model with an explicit definition/runtime split.
* Curated, data-authored scenario library.
* Provider abstraction, Telegram-adapter separation, and dual persistence preserved.

### Negative

* Existing playthroughs from the character-centric era are not migrated.

### Follow-up (completed)

* The character-centric dead code was removed: legacy `Session`/`SessionStore` (+ JSON and
  PostgreSQL stores), `CharacterService`/`CharacterCommandService`, `CharacterStore` (+
  stores), `SelectCharacterCommand`, `character_card`, and the `invocation_policy` module.
  The `sessions`, `active_sessions`, and `characters` tables were dropped (Alembic
  `20260722_0004`). The `Character`/`CharacterVisibility` domain entities remain, as
  scenarios embed characters. `WorldStore` and the conversation summarizer are left in
  place but are no longer wired into the runtime.

## Supersedes

* Supersedes ADR-020 (Conversation Ownership and Identity Scope) where it made `Session`
  bind `owner + character + world`; ownership is now `ScenarioSession` → `ScenarioDefinition`.
* Narrows ADR-022 (Character Card v3): the character card remains the portable character
  asset format, but characters are now scenario assets rather than the root entity.

---

# ADR-024 — Postgres as Sole Persistence Backend

**Status:** Accepted

**Date:** 2026-07-24

## Context

ADR-023 established dual persistence — JSON and PostgreSQL kept at parity behind a shared
serializer and one contract-test suite run against both backends — as a deliberate
transitional strategy while the scenario-centric model and the Postgres store
implementations were being built out. That build-out is now done (S001–S008): every store
port has a `Postgres*Store` implementation, migrations are integrity-tested against a real
DB (S006), a startup health probe exists (S007), and a one-time JSON→Postgres migration
script has shipped for existing deployments. `RP_ENGINE_PERSISTENCE_BACKEND` still defaults
to `"json"`, so the transitional dual-backend state has outlived its purpose.

This came to a head planning S010 (admin panel scenario-catalog editing), whose open
question was "does an edited scenario live in Postgres or get written back to JSON?" —
which turned out to be deeper than a config default. Today `PlaythroughService` lists and
starts scenarios from an in-memory `ScenarioCatalog` loaded once at boot from a curated JSON
directory (`app/main.py` → `ScenarioCatalog.from_directories(settings.scenario_catalog_dirs)`);
`ScenarioDefinitionStore` (JSON or Postgres, whichever backend is active) is only ever
written to as a derived cache once a playthrough begins
(`playthrough_service.py::_begin` → `self._scenario_definition_store.save(scenario)`), and
read back only as a fallback in `restart`. So a hypothetical admin panel that wrote scenario
edits into `ScenarioDefinitionStore` would not actually make them playable — `/play` would
keep serving the stale catalog copy. Two parallel scenario sources, not one, is the actual
problem dual persistence left unresolved.

## Decision

**Postgres becomes the only runtime persistence backend.** Concretely:

* All six JSON store implementations (`storage/json_scenario_definition_store.py`,
  `json_scenario_session_store.py`, `json_conversation_store.py`, `json_user_identity_store.py`,
  `json_group_identity_store.py`, `json_generation_trace_store.py`) are **deleted**, not
  deprecated. `Settings.persistence_backend` and the branch in `build_container` are removed;
  the composition root wires the Postgres stores unconditionally. This follows the same
  no-back-compat precedent ADR-023 set for the character→scenario cutover: the project is
  pre-release, and carrying a second live backend costs more (surface area, the contract-test
  matrix, the "which one is source of truth" ambiguity above) than it returns.
* **`ScenarioDefinitionStore` becomes the live source for scenario listing/starting/resuming.**
  `PlaythroughService` is rewired to query the store directly (`find_by_owner` /
  `get_by_id`) instead of `ScenarioCatalog`; the `catalog` constructor parameter and the
  catalog wiring in `build_container` are removed. This closes the two-sources-of-truth gap
  above and is the change that actually resolves S010: the admin panel writes scenarios into
  `ScenarioDefinitionStore`, and `/play` sees them immediately because it reads from the same
  place.
* **`ScenarioCatalog`'s JSON-loading code is repurposed, not deleted.** Its directory-walking
  and validation logic becomes the basis of a scenario **import/export utility** exposed as an
  admin panel feature: import pushes JSON scenario payloads into `ScenarioDefinitionStore`
  (used once to seed a fresh DB with the existing curated set, and afterward for
  bringing in new hand-authored scenarios); export serializes a stored scenario back to the
  same JSON shape for backup/portability. The same import/export treatment extends to
  `ScenarioSession` (+ its conversation transcript), for backing up or restoring a
  playthrough. Once a scenario has been imported, Postgres is authoritative — the admin panel
  is the only place scenarios and sessions are *authored/edited* going forward; JSON is a
  transfer format, not a live source.
* **The test suite gains an auto-managed Postgres fixture** (e.g. testcontainers) so
  `uv run pytest` keeps working with no manual `docker compose up` step. The JSON leg of the
  shared contract-test suite (`tests/.../contracts/`) is deleted; the Postgres contract run
  becomes the only one and stops being gated behind `RP_ENGINE_RUN_POSTGRES_TESTS` for the
  default `pytest` invocation (a separate live-DB-only suite may still exist for anything the
  managed fixture can't cover, e.g. real-migration integrity tests per S006).
* The detailed cutover (deleting the JSON stores, rewiring `PlaythroughService`, building the
  import/export utility, wiring the test fixture) is tracked as its own epic,
  `.devloop/epics/S013-retire-json-persistence.md`, since it spans more than S010's
  admin-panel slice. S010 depends on it.

## Alternatives

* **Keep JSON as a supported offline/local-dev mode** (Postgres default, JSON opt-in) —
  rejected: it preserves exactly the "two sources of truth" ambiguity this ADR exists to
  remove, for a use case (zero-dependency local trial) the new testcontainers-backed test
  fixture and `scripts/db_services.sh` already cover with one `docker compose up`.
* **Deprecate now, delete later** (flip the default, leave JSON code in place, remove it in a
  follow-up story) — rejected: for a pre-release codebase, a half-removed backend is worse
  than either fully-present or fully-gone — it still has to be reasoned about but no longer
  gets test coverage. Matches the one-shot removal precedent from ADR-023's own follow-up
  cleanup.

## Rationale

* Removes the actual ambiguity blocking S010: one scenario source, not two.
* Matches the project's stated no-v1-back-compat stance (ADR-023) rather than introducing a
  new instance of exactly the parallel-path problem that ADR rejected.
* Recycles rather than discards the JSON catalog code — it becomes the import/export path
  instead of dead weight.
* Simplifies the composition root and shrinks the contract-test matrix from "two backends,
  kept at parity" to "one backend, tested directly."

## Consequences

### Positive

* Single, unambiguous source of truth for scenarios and sessions — unblocks S010.
* `build_container`, `Settings`, and the contract-test suite all get simpler.
* The recycled catalog code gives the admin panel a real import/export feature instead of
  being retired outright.

### Negative

* Postgres becomes a hard dependency to run the app or the test suite at all — there is no
  more zero-setup JSON fallback. Mitigated by the testcontainers-backed pytest fixture and
  `scripts/db_services.sh`, but it's a real loss of the "just clone and run" simplicity ADR-001
  (Local-First Architecture) valued; Postgres itself stays local (docker compose), so the
  local-first *principle* holds, but the on-ramp gets heavier.
* A fresh/empty Postgres database has no curated scenarios until the import step runs once —
  unlike today, where the JSON catalog directory ships them for free at every boot. The
  import/export utility (S013) must exist before or alongside the JSON-store deletion, not
  after, or `/play` regresses to empty on a fresh deploy.
* `PlaythroughService`, `build_container`, and every JSON store's call sites need updating in
  the same change — this is not a config-only flip.

## Supersedes

* Supersedes the dual-persistence-backend decision in ADR-023 ("Both persistence backends...
  kept at parity via a shared serializer and one contract-test suite run against both
  backends"). ADR-023's scenario-centric domain model itself is unaffected.
