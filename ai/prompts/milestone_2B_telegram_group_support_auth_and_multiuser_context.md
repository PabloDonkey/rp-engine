# Milestone 2B — Telegram Group Support, Authorization, and Multi-User Context

You are implementing the next RP Engine milestone.

Before making changes, read:

* README.md
* docs/VISION.md
* docs/SPEC.md
* docs/ARCHITECTURE.md
* docs/DECISIONS.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

The goal of this milestone is to improve Telegram behavior for groups and preserve multi-user context.

Do not redesign the architecture.

---

# Architecture Rules

Telegram-specific behavior belongs in:

```text
src/rp_engine/adapters/telegram/
```

The core engine must not know:

* Telegram user IDs
* Telegram group IDs
* Telegram administrators
* Telegram commands
* Telegram permissions

The adapter translates Telegram concepts into application use cases.

---

# Authorization Model

Implement two different authorization modes.

---

# Private Chats

Private chats require user authorization.

Flow:

```text
Telegram private message

        ↓

Check user_id whitelist

        ↓

Authorized?

   Yes → process message

   No → send private beta message
```

Unauthorized response:

```text
Hi! 👋 This bot is currently in a private beta and isn't accepting new users yet. If you'd like access, please contact @pablodonkey on Telegram. Thanks for your interest!
```

Make this configurable through settings.

---

# Group Chats

Groups use group-level authorization.

A whitelisted group allows all members to interact.

Flow:

```text
Telegram group message

        ↓

Check group_id whitelist

        ↓

Authorized group?

   Yes → allow members

   No → ignore or send configured message
```

Important:

If a group is authorized:

* individual users do NOT need to be whitelisted
* all members can interact with the bot

---

# Group Commands

Commands with destructive or story-control effects require administrator permissions.

Required behavior:

| Command        | Private         | Group                        |
| -------------- | --------------- | ---------------------------- |
| normal message | authorized user | any user in authorized group |
| /help          | everyone        | everyone                     |
| /continue      | authorized user | group admin only             |
| /clear         | authorized user | group admin only             |

The adapter must verify Telegram administrator status.

Do not move this logic into the core.

---

# Conversation Identity

Conversation identity should be resolved by the Telegram adapter.

Private chat:

```text
memory_key = user_id
```

Group chat:

```text
memory_key = group_id
```

The core only receives the conversation identity.

It does not know whether it came from Telegram.

---

# Multi-User Group Messages

The LLM needs to know which human is speaking.

Do not store only plain text.

Extend stored messages with metadata.

Example:

```json
{
  "role": "user",
  "user_id": 123456,
  "username": "alice",
  "display_name": "Alice",
  "content": "I open the door"
}
```

For assistant messages:

```json
{
  "role": "assistant",
  "content": "The door creaks open..."
}
```

---

# Message Formatting

Do not permanently inject usernames into stored content.

Bad:

```json
{
  "content": "Alice said: I open the door"
}
```

Good:

```json
{
  "username": "Alice",
  "content": "I open the door"
}
```

The memory strategy or prompt builder should decide how to render messages.

For group prompts, render:

```text
Alice said:
I open the door

Bob said:
What is inside?
```

For private chats:

```text
User:
I open the door
```

---

# Commands

Maintain the existing architecture:

Telegram commands are interpreted by the adapter.

The LLM must never receive:

```text
/continue
/clear
/help
```

---

# /continue

Behavior:

1. Adapter receives `/continue`.
2. Adapter validates permissions.
3. Adapter calls:

```python
ChatService.continue_story(...)
```

4. Engine generates continuation.
5. Only the assistant response is saved.

Do not store:

```text
/continue
```

Do not store:

```text
Continue the narration naturally from the current context.
```

The continuation instruction is generation metadata only.

---

# /clear

Behavior:

1. Adapter receives `/clear`.
2. Adapter validates permissions.
3. Adapter calls:

```python
ChatService.clear_conversation(...)
```

4. Confirm success.

Example:

```text
Conversation memory cleared.
```

---

# Configuration

Update settings and `.env.example`.

Add support for:

```env
TELEGRAM_ALLOWED_USERS=
TELEGRAM_ALLOWED_GROUPS=
TELEGRAM_UNAUTHORIZED_MESSAGE=
```

Use appropriate types:

```python
set[int]
```

Avoid comma-separated string handling outside configuration parsing.

---

# Tests

Add tests for:

## Authorization

* private authorized user accepted
* private unauthorized user rejected
* authorized group accepts all users
* unauthorized group rejected

## Permissions

* group admin can clear
* group member cannot clear
* group admin can continue
* group member cannot continue

## Message metadata

Verify:

* username stored separately
* user_id stored separately
* content remains clean

## Routing

Verify:

* commands never reach the LLM
* normal group messages reach ChatService
* unauthorized messages do not reach ChatService

Mock Telegram API calls.

---

# Documentation

Update:

## ARCHITECTURE.md

Document:

* Telegram authorization boundary
* group identity handling
* command ownership
* multi-user message metadata

---

## DECISIONS.md

Add:

## ADR-014 — Group Authorization Uses Conversation Identity

Decision:

For group conversations, authorization is performed at the group level. Individual users inherit access from the authorized group.

---

## ADR-015 — Store User Metadata Separately From Message Content

Decision:

Conversation messages store identity metadata separately from text content. Formatting for LLM prompts happens later.

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
* assumptions
