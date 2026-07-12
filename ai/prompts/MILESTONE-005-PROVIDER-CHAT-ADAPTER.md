# Milestone 005 — Provider Chat Adapter

## Goal

Adapt the LLM provider layer to consume the new provider-independent `Conversation` model.

The core engine now produces structured conversations. This milestone makes the infrastructure layer responsible for translating those conversations into the format required by the selected LLM provider.

After this milestone:

* The core engine does not know about LM Studio.
* `LMStudioProvider` converts domain conversations into `lms.Chat`.
* The provider interface accepts conversations instead of prompt strings.
* Generation settings are separated from conversation data.
* Future providers can implement their own adapters.

---

# Motivation

Before:

```text
 id="v9s6s0"
ConversationBuilder
        |
        v
string prompt
        |
        v
LMStudioProvider
```

After:

```text
 id="x9a2l5"
ConversationBuilder
        |
        v
Conversation
        |
        v
LLMProvider
        |
        v
Provider Adapter
        |
        v
LLM SDK
```

The provider layer becomes a translation boundary.

---

# Architecture

Target flow:

```text
 id="y0w8wv"
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
        |
        v
LMStudioProvider
        |
        v
lms.Chat
        |
        v
LM Studio
```

---

# Update LLMProvider Interface

## Before

Current:

```python
generate(prompt: str)
```

Problem:

* Provider receives formatted text.
* Chat structure is lost.
* Provider-specific features are harder to use.

---

## After

Change to:

```python
generate(
    conversation: Conversation,
    settings: GenerationSettings
) -> LLMResponse
```

The interface accepts domain objects only.

---

# Add Generation Settings

Generation parameters should not be mixed with conversation data.

Create:

```text
 id="7dd4mq"
core/
└── llm/
    └── generation.py
```

Example:

```python
GenerationSettings
├── temperature
├── max_tokens
├── top_p
└── stop_sequences
```

The same settings object can later be translated by different providers.

---

# LMStudioProvider

The LM Studio SDK belongs only here.

Example responsibility:

```text
 id="n1h5qv"
Conversation
      |
      v
LMStudioProvider
      |
      v
lms.Chat
```

The provider translates roles.

---

# Role Mapping

Domain roles:

```text
 id="f7q9mn"
SYSTEM
USER
CHARACTER
```

LM Studio roles:

```text
 id="1y1j3h"
system
user
assistant
```

Mapping:

| Domain    | LM Studio |
| --------- | --------- |
| SYSTEM    | system    |
| USER      | user      |
| CHARACTER | assistant |

The role conversion must exist only inside the provider adapter.

---

# Example Translation

Domain conversation:

```text
 id="m3x5v1"
SYSTEM
You are Belzebuth.

USER
Hello.

CHARACTER
Hello Pablo.
```

LM Studio chat:

```text
 id="f1g4s2"
system:
You are Belzebuth.

user:
Hello.

assistant:
Hello Pablo.
```

The core never sees this conversion.

---

# Create Conversation Translator

Avoid putting conversion logic directly inside the provider.

Create:

```text
 id="6v0m8q"
infrastructure/
└── llm/
    └── lmstudio/
        ├── provider.py
        └── conversation_mapper.py
```

Responsibility:

```python
map_conversation(
    conversation: Conversation
) -> lms.Chat
```

Example:

```python
for message in conversation.messages:
    if message.role == SYSTEM:
        chat.system(message.content)

    elif message.role == USER:
        chat.user(message.content)

    elif message.role == CHARACTER:
        chat.assistant(message.content)
```

---

# Provider Response Model

Do not expose SDK responses.

Create a domain/application response:

```text
 id="5m9f9h"
LLMResponse
├── content
├── finish_reason
└── metadata
```

Example:

```python
LLMResponse(
    content="Hello Pablo.",
    finish_reason="stop"
)
```

The application should not receive:

```python
lms.PredictionResult
```

---

# Handle Token Limit Completion

The provider should expose when generation stops because of length.

Example:

```python
finish_reason = "length"
```

The application can later decide:

* request continuation
* display continue button
* summarize

Do not implement automatic continuation yet.

---

# Error Handling

Provider errors must be converted.

Do not leak:

```python
LMStudioException
```

outside infrastructure.

Create provider-independent errors:

```python
LLMConnectionError
LLMGenerationError
LLMTimeoutError
```

---

# Refactor Orchestrator

Before:

```python
prompt = prompt_builder.build(context)

response = llm.generate(prompt)
```

After:

```python
conversation = conversation_builder.build(context)

response = llm.generate(
    conversation,
    settings
)
```

---

# Tests

## Conversation Mapping

Verify:

Input:

```text
CHARACTER
Hello
```

Produces:

```text
assistant:
Hello
```

---

## Provider Isolation

Verify:

Core tests do not import:

* LM Studio SDK
* provider classes

---

## Generation Settings

Verify:

* Settings are passed correctly.
* Provider applies them.

---

## Finish Reason

Verify:

A length-limited generation returns:

```python
finish_reason="length"
```

---

# Documentation Updates

Update:

* `ARCHITECTURE.md`
* `DOMAIN_MODEL.md`
* `DECISIONS.md`

Document:

* Provider translation boundary.
* Domain roles vs provider roles.
* LLMResponse abstraction.

Add ADR if needed:

## Provider Owns Conversation Serialization

The provider adapter is responsible for translating domain conversations into SDK-specific formats.

---

# Constraints

* No LM Studio imports outside infrastructure.
* No `lms.Chat` in application or domain.
* No provider-specific response objects exposed.
* Conversation role mapping remains inside adapters.
* Keep LLM provider replacement possible.

---

# Success Criteria

This milestone is complete when:

* `Conversation` reaches the provider layer.
* LM Studio receives native chat history.
* The engine no longer builds LLM prompts.
* Provider-specific code is isolated.
* Another provider could be added without changing the core.
