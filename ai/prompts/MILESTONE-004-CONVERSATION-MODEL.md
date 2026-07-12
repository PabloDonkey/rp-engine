# Milestone 004 — Conversation Model

## Goal

Replace the current string-based prompt construction system with a provider-independent conversation model.

The engine should no longer generate a single formatted prompt string.

Instead:

```text
Domain Context
      |
      v
ConversationBuilder
      |
      v
Conversation
      |
      v
LLM Provider
```

The conversation model becomes the boundary between the roleplay engine and LLM providers.

---

# Motivation

Current architecture:

```text
Session
   |
   v
PromptBuilder
   |
   v
string prompt
   |
   v
LLM Provider
```

Problems:

* Conversation structure is lost.
* Providers cannot use native chat APIs correctly.
* Domain logic becomes mixed with prompt formatting.
* Adding another provider requires rebuilding prompts.

Target:

```text
Session
   |
   v
ConversationBuilder
   |
   v
Conversation
   |
   v
Provider Adapter
```

---

# Design Principles

## Domain does not know providers

The domain must not import:

* LM Studio SDK
* OpenAI SDK
* Anthropic SDK
* Any provider-specific message classes

The domain only knows:

* system instructions
* user messages
* character messages

---

## Domain uses roleplay terminology

The engine is not talking to an assistant.

The engine is simulating a character.

Domain roles:

```text
SYSTEM
USER
CHARACTER
```

Do not create:

```text
ASSISTANT
```

inside the domain.

The provider will translate:

```text
CHARACTER → assistant
```

when required.

---

# Domain Structure

Create:

```text
core/
└── conversation/
    ├── conversation.py
    ├── message.py
    ├── role.py
    └── builder.py
```

---

# ConversationRole

Create an enum representing domain roles.

Example:

```python
ConversationRole.SYSTEM
ConversationRole.USER
ConversationRole.CHARACTER
```

Responsibilities:

* Describe who is speaking.
* Remain independent from LLM APIs.

---

# ConversationMessage

Represents a single conversation entry.

Example:

```python
ConversationMessage
├── role
├── content
└── metadata
```

Example:

```json
{
    "role": "character",
    "content": "Welcome back, Pablo."
}
```

---

## Metadata

Prepare for future extensions.

Possible future fields:

* message ID
* timestamp
* source
* tool calls
* attachments
* visibility

Avoid designs that require replacing the model later.

---

# Conversation Entity

Represents the complete context sent to the LLM.

Example:

```python
Conversation
├── messages
└── metadata
```

Example:

```text
SYSTEM
Character definition

SYSTEM
World information

SYSTEM
Memory summary

CHARACTER
Hello Pablo.

USER
Hello Belzebuth.

CHARACTER
Good to see you again.
```

---

# ConversationBuilder

Replace:

```text
PromptBuilder
```

with:

```text
ConversationBuilder
```

Responsibility:

Transform domain objects into a Conversation.

Inputs:

```python
build(
    session,
    user,
    character,
    world,
    memory
) -> Conversation
```

---

# Conversation Building Flow

Example:

```text
Session
 |
 +-- User
 |
 +-- Character
 |
 +-- World
 |
 +-- Memory
 |
 v
ConversationBuilder
 |
 v
Conversation
```

---

# Template Resolution

Character and world data may contain:

```text
{{char}}
{{user}}
```

The builder resolves them.

Example:

Before:

```text
{{char}} is a dragon companion.
{{user}} is an adventurer.
```

After:

```text
Belzebuth is a dragon companion.
Pablo is an adventurer.
```

The final Conversation should not contain unresolved templates.

---

# Message Ordering

The builder controls message order.

Recommended order:

```text
SYSTEM
    Character card

SYSTEM
    World information

SYSTEM
    Memory summary

CHARACTER
    Previous assistant response

USER
    Current user message
```

The exact order may evolve based on model behavior.

---

# Conversation History

History should no longer be stored as raw strings.

Old:

```json
[
    "User: hello",
    "Assistant: hi"
]
```

New:

```json
[
    {
        "role": "user",
        "content": "hello"
    },
    {
        "role": "character",
        "content": "hi"
    }
]
```

---

# Storage Changes

Prepare history storage for structured messages.

Example:

```text
data/
└── sessions/
    └── <session_id>/
        ├── session.json
        └── history.jsonl
```

Example history entry:

```json
{
    "role": "character",
    "content": "Hello again."
}
```

---

# Application Flow

New runtime flow:

```text
Telegram Adapter
        |
        v
ChatService
        |
        v
ConversationBuilder
        |
        v
Conversation
        |
        v
LLMProvider
```

---

# Replace Existing Components

Remove dependency on:

```python
PromptBuilder.build() -> str
```

Replace with:

```python
ConversationBuilder.build() -> Conversation
```

---

# Provider Interface Preparation

Update the provider abstraction.

Before:

```python
generate(prompt: str)
```

After:

```python
generate(conversation: Conversation)
```

The provider will later translate this into its own format.

---

# Constraints

* No provider SDK imports in core.
* No LM Studio objects in domain models.
* No "assistant" role in the domain.
* No unresolved `{{char}}` or `{{user}}` placeholders after building.
* ConversationBuilder owns assembly logic.
* History is structured data.

---

# Tests

## ConversationRole

Verify:

* Valid domain roles exist.
* No provider-specific roles exist.

---

## ConversationBuilder

Verify:

Input:

```text
Character:
Belzebuth

User:
Pablo
```

Produces:

```text
SYSTEM
Belzebuth...

USER
Pablo...
```

---

## Template Resolution

Verify:

Input:

```text
{{char}} likes {{user}}
```

Produces:

```text
Belzebuth likes Pablo
```

---

## History Conversion

Verify:

Old session history can migrate into:

```text
ConversationMessage[]
```

---

## Isolation Test

Verify:

ConversationBuilder works without:

* Telegram imports
* LM Studio imports
* Provider SDKs

---

# Documentation Updates

Update:

* `DOMAIN_MODEL.md`
* `ARCHITECTURE.md`
* `DECISIONS.md`

Document:

* Domain conversation roles.
* Provider role translation.
* ConversationBuilder responsibility.

---

# Success Criteria

This milestone is complete when:

* The engine builds structured conversations.
* Prompt strings are no longer the main abstraction.
* Roleplay concepts are represented explicitly.
* Conversation history is structured.
* Providers can consume conversations without changing the core.
