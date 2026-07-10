# Milestone 1.5 — Developer Experience and Debugging

You are continuing development of RP Engine after Milestone 1.

Read:

* README.md
* docs/VISION.md
* docs/SPEC.md
* docs/ARCHITECTURE.md
* docs/DECISIONS.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

---

# Objective

Improve developer visibility.

The system should make it easy to answer:

* Is the application running?
* Is LM Studio reachable?
* Is Telegram connected?
* What dependencies are active?
* What happens during a message flow?

Do not add new RP features.

---

# 1. Add health endpoint

Create:

```text
GET /health
```

Location:

```text
src/rp_engine/app/
```

Return application status.

Example:

```json
{
  "status": "ok",
  "services": {
    "llm": "available",
    "telegram": "running"
  }
}
```

Do not expose secrets.

---

# 2. Add structured logging

Add logging around:

Application startup:

```text
Application starting
Configuration loaded
Dependencies created
Telegram adapter started
```

Message flow:

```text
Telegram message received
ChatService called
Orchestrator started
LLM request sent
Response generated
```

Errors:

```text
LLM unavailable
Telegram failure
Configuration error
```

Use Python standard logging unless there is a strong reason not to.

---

# 3. Add debug information support

Create a debug-friendly way to inspect runtime state.

Possible endpoint:

```text
GET /debug/status
```

or an internal debug service.

Expose only:

* loaded model name
* application state
* enabled adapters

Do not expose:

* tokens
* user secrets
* private conversations

---

# 4. Improve configuration validation

Verify:

* missing Telegram token behavior
* missing LM Studio configuration behavior
* invalid values produce clear errors

Development mode should allow running without Telegram enabled.

---

# 5. Add tests

Add tests for:

* health endpoint
* configuration validation
* startup lifecycle
* debug status

Use mocks for external services.

---

# Constraints

Do not:

* Add databases
* Add memory systems
* Add character systems
* Add world simulation
* Add vector databases

Keep the architecture unchanged.

---

# Validation

Run:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```

Provide:

* files created
* files modified
* test results
* developer workflow improvements
