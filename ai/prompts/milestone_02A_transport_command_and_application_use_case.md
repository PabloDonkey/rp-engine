# Milestone 2A — Transport Commands and Application Use Cases

You are implementing the next architectural milestone of RP Engine.

Before making changes, read:

* README.md
* docs/VISION.md
* docs/SPEC.md
* docs/ARCHITECTURE.md
* docs/DECISIONS.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

The current application works.

The goal of this milestone is to improve the architecture, not to add RP features.

---

# Objective

Transport-specific commands belong to adapters.

Application behavior belongs to application services.

The RP Engine must never know about Telegram commands.

---

# Architectural Rules

Adapters are responsible for:

* parsing transport syntax
* authorization
* invocation policy
* translating transport actions into application use cases

Adapters are **not** responsible for:

* RP logic
* prompt construction
* memory logic
* LLM interaction

---

# Application Use Cases

The application layer must expose explicit use cases.

Instead of designing around HTTP endpoints, design around application operations.

For example:

```python
ChatService.send_message(...)

ChatService.continue_story(...)

ChatService.clear_conversation(...)
```

Adapters call these methods directly.

FastAPI endpoints call these methods directly.

The HTTP API is simply another adapter over the same application services.

Avoid coupling business logic to HTTP routes.

---

# Desired Flow

Private chat:

```text
User message
        ↓
Telegram Adapter
        ↓
ChatService.send_message()
        ↓
RP Engine
```

Continue:

```text
/continue
        ↓
Telegram Adapter
        ↓
ChatService.continue_story()
        ↓
RP Engine
```

Clear:

```text
/clear
        ↓
Telegram Adapter
        ↓
ChatService.clear_conversation()
```

Help:

```text
/help
        ↓
Telegram Adapter
        ↓
Telegram reply
```

The help command never reaches the application layer.

---

# Telegram Adapter

Refactor into small responsibilities.

Suggested structure:

```text
adapters/
└── telegram/
    ├── adapter.py
    ├── commands.py
    ├── authorization.py
    ├── invocation_policy.py
    └── models.py
```

---

# Invocation Policy

Private chats:

* normal messages are processed
* commands are processed

Group chats:

* normal messages are ignored
* only supported commands are processed

---

# Authorization

Support whitelist configuration.

Authorized users proceed normally.

Unauthorized users receive the configured message:

> Hi! 👋 This bot is currently in a private beta and isn't accepting new users yet. If you'd like access, please contact @pablodonkey on Telegram. Thanks for your interest!

Make the message configurable through settings.

---

# Supported Commands

Implement:

## /help

Handled entirely by the Telegram adapter.

Do not call ChatService.

Display available commands.

---

## /continue

The adapter translates the command into:

```python
ChatService.continue_story(...)
```

The literal `/continue` command must never be sent to the LLM.

The literal `/continue` command must never be stored in memory.

The temporary continuation instruction is generation metadata only.

Only the assistant response is persisted.

---

## /clear

Translate into:

```python
ChatService.clear_conversation(...)
```

Return a confirmation message to the user.

---

# FastAPI

FastAPI is another adapter.

Its responsibility is translating HTTP requests into application use cases.

Example mappings:

```text
POST /chat
        ↓
ChatService.send_message()

POST /continue
        ↓
ChatService.continue_story()

POST /memory/clear
        ↓
ChatService.clear_conversation()
```

The endpoints should contain little or no business logic.

---

# Documentation

Update:

## ARCHITECTURE.md

Document:

* adapter responsibilities
* application use cases
* transport translation
* invocation policy
* authorization flow

---

## DECISIONS.md

Add:

### ADR-013 — Transport Commands Belong to Adapters

Transport-specific syntax belongs to adapters.

The application exposes transport-agnostic use cases.

The core engine remains unaware of Telegram, HTTP, or slash commands.

---

# Tests

Add tests covering:

* command parser
* authorization
* invocation policy
* help command
* continue command
* clear command

Verify:

* `/continue` never reaches the LLM
* `/continue` is not stored in memory
* `/help` never calls ChatService
* `/clear` clears the conversation
* private chats accept normal messages
* group chats ignore normal messages
* group commands continue to function

Mock Telegram and LM Studio.

---

# Validation

Run:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```

Report:

* files created
* files modified
* architecture changes
* test results
* any assumptions or tradeoffs before implementation
