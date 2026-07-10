# Milestone 1 Telegram Validation

You are validating the first real end-to-end execution path of RP Engine.

The architecture is already implemented.

Do not redesign the architecture.

The goal is to run the application with a real Telegram bot token and verify the complete message flow.

---

## Read First

Review:

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

Make the project runnable locally with:

```text
Telegram User
      |
      v
Telegram Bot
      |
      v
Telegram Adapter
      |
      v
ChatService
      |
      v
RPOrchestrator
      |
      v
LMStudioProvider
      |
      v
LM Studio
```

---

# Tasks

## 1. Configure environment example

Review:

```text
.env.example
```

Make it complete.

It must document all required environment variables.

Expected categories:

## Application

Example:

```env
APP_ENV=development
LOG_LEVEL=INFO
```

## Telegram

Example:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
```

## LM Studio

Example:

```env
LMSTUDIO_HOST=http://localhost:1234
LMSTUDIO_MODEL=
```

Do not put real secrets in `.env.example`.

---

## 2. Verify `.env` loading

Confirm:

* `.env` is loaded automatically in development.
* Missing required values produce useful errors.
* Telegram can be disabled for tests/local development.

Do not expose secrets in logs.

---

## 3. Verify startup command

Document exactly how to start the application.

Update:

```text
README.md
```

Include:

## Installation

Example:

```bash
uv sync
```

## Environment setup

Example:

```bash
cp .env.example .env
```

Explain that the user must edit `.env`.

## Run application

Provide the exact command.

Example:

```bash
uv run python -m rp_engine.app.main
```

or the correct command based on the actual project entry point.

Do not guess. Verify the correct command from the code.

---

## 4. Add useful startup logs

When starting the application, logs should clearly show:

Example:

```
Starting RP Engine
Environment loaded
LM Studio provider initialized
Telegram adapter enabled
Telegram polling started
Application ready
```

Do not log:

* Telegram token
* private messages
* secrets

---

## 5. Verify Telegram adapter

Review:

```text
src/rp_engine/adapters/telegram/
```

Confirm:

* Incoming Telegram messages reach ChatService.
* Responses are sent back.
* Adapter does not directly call LM Studio.
* Adapter does not create core services.

---

## 6. Add a manual validation checklist

Add to README:

```markdown
## First Run Test

1. Start LM Studio.
2. Load a model.
3. Start RP Engine.
4. Open Telegram.
5. Send a message to the bot.
6. Confirm a response is received.
```

---

# Testing

Run:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```

Then provide:

* startup command
* required environment variables
* files modified
* test results
* manual test procedure

---

# Constraints

Do not:

* Add memory
* Add character systems
* Add databases
* Add new frameworks
* Change architecture

This is only an operational validation milestone.
