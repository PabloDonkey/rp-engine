# Milestone 1 Hardening — Architecture Review and Stabilization

You are working on the RP Engine repository.

Before making changes, read:

* README.md
* docs/VISION.md
* docs/SPEC.md
* docs/ARCHITECTURE.md
* docs/DECISIONS.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

Current state:

Milestone 1 vertical slice is complete:

Telegram Adapter
↓
ChatService
↓
RPOrchestrator
↓
LLMProvider
↓
LMStudioProvider

Tests and quality checks currently pass.

The goal of this task is not to add features.
The goal is to validate and strengthen the architecture.

---

# Objectives

## 1. Move LLM abstraction to the correct layer

Review the current LLM provider abstraction.

The desired architecture:

```text
core/
    ports/
        llm_provider.py

infrastructure/
    llm/
        lmstudio_provider.py
```

Rules:

* Core defines the contract.
* Infrastructure implements the contract.
* Core must not import infrastructure.
* Infrastructure may depend on core abstractions.

The interface should remain minimal.

Example:

```python
class LLMProvider(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]]
    ) -> str:
        ...
```

Only move/refactor if the current implementation violates this dependency direction.

---

## 2. Review Telegram lifecycle ownership

Review:

```text
src/rp_engine/app/lifespan.py
src/rp_engine/adapters/telegram/
```

Verify:

* app owns startup and shutdown
* Telegram adapter does not create application services
* Telegram adapter does not initialize infrastructure
* Telegram polling lifecycle is cleanly started/stopped

Desired flow:

```text
app lifespan

    starts

Telegram adapter runtime

    uses

ChatService

    uses

Core
```

Avoid:

```text
Telegram adapter
    starting
    application
```

---

## 3. Add an application smoke test

Create an integration-style smoke test.

Location:

```text
tests/integration/test_application_flow.py
```

Purpose:

Verify the complete internal flow without external services.

Test:

```text
fake Telegram message
        ↓
Telegram adapter
        ↓
ChatService
        ↓
RPOrchestrator
        ↓
Fake LLMProvider
        ↓
response returned
```

Requirements:

* Do not call Telegram API.
* Do not call LM Studio.
* Use dependency injection/mocks.
* Verify the boundaries work together.

---

## 4. Update documentation

Update:

### docs/ARCHITECTURE.md

Document:

* composition root
* provider abstraction
* dependency direction
* Telegram lifecycle ownership

---

### docs/DECISIONS.md

Add an ADR:

```text
ADR-011 — Application Composition Root
```

Decision:

The application layer owns dependency creation and lifecycle management.

---

### docs/ROADMAP.md

Mark Milestone 1 completed.

Include:

* Telegram adapter
* LM Studio SDK integration
* provider abstraction
* tests
* quality tooling

---

# Constraints

Do not:

* Add memory
* Add characters
* Add world state
* Add databases
* Add vector search
* Add agent frameworks

Do not redesign the architecture.

Only improve correctness and maintainability.

---

# Validation

After changes run:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```

Report:

* files changed
* architecture changes
* test results
* remaining concerns
