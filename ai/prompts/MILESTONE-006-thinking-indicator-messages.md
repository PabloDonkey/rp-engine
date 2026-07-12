Here is the revised milestone with the feedback capability modeled as a port, while keeping Telegram-specific behavior inside the Telegram adapter.

```md
# Milestone 006 — Processing Feedback Port & Adapter Implementations

## Goal

Provide a generic mechanism for notifying users that the assistant is currently processing a request.

Long-running LLM inference should provide feedback through the active adapter without coupling the RP engine to a specific transport.

The system should support:

- typing/thinking indicators,
- temporary status messages,
- personality-driven waiting messages,
- future progress updates.

---

# Motivation

Local LLM inference can take several seconds or more.

Without feedback:

- users may think the bot is frozen,
- users may resend messages,
- the experience feels disconnected.

Processing feedback turns waiting time into part of the assistant experience.

Example:

```

Tord is deciding whether Pablo deserves an answer...

```

instead of:

```

(waiting silently for 40 seconds)

```

---

# Architecture

## Responsibility boundaries

```

Adapter

```
|
▼
```

Processing Feedback Implementation

```
|
▼
```

Processing Feedback Port

```
|
▼
```

Application Layer

```
|
▼
```

RP Engine

````

The RP engine does not know about:

- Telegram
- Discord
- web clients
- typing indicators
- temporary messages

The application layer only knows:

"the user should receive processing feedback."

---

# Design Principle

The system should express capabilities, not transports.

Bad:

```python
telegram_bot.send_typing()
````

Good:

```python
processing_feedback.start()
```

The adapter decides how that capability is implemented.

---

# Processing Feedback Port

Create an application port representing processing feedback.

Example:

```python
class ProcessingFeedback(Protocol):

    async def start(
        self,
        context: FeedbackContext
    ) -> None:
        ...

    async def update(
        self,
        message: str
    ) -> None:
        ...

    async def stop(self) -> None:
        ...
```

Responsibilities:

* notify that processing started,
* optionally update the status,
* cleanly finish processing feedback.

The port must not contain:

* Telegram API calls,
* Discord API calls,
* UI rendering logic.

---

# Feedback Lifecycle

Example:

```
User sends message

        |
        ▼

feedback.start()

        |
        ▼

Run memory retrieval

        |
        ▼

Build prompt

        |
        ▼

Run LLM inference

        |
        ▼

feedback.stop()

        |
        ▼

Send final response
```

---

# Application Integration

The application orchestration owns the lifecycle.

Example:

```python
async with processing_feedback.processing(context):

    response = await chat_service.process(
        message
    )
```

The application does not know whether feedback is implemented by:

* Telegram typing status,
* Discord typing event,
* web loading indicator.

---

# Telegram Adapter Implementation

Location:

```
adapters/

└── telegram/

    └── feedback.py
```

Telegram implementation responsibilities:

* send `ChatAction.TYPING`,
* refresh typing status periodically,
* send temporary messages,
* delete temporary messages,
* cleanup after errors.

Example:

```
Telegram:

Tord is searching his memories...

Tord is typing...

(final answer)
```

---

# Typing Indicator

Telegram typing status expires quickly.

Implementation:

```
start

    |
    ▼

send typing action

    |
    ▼

wait ~4 seconds

    |
    ▼

repeat

    |
    ▼

stop after response
```

The refresh loop must be cancelled when inference finishes.

---

# Temporary Processing Messages

Before inference:

Send a temporary message.

Example:

```
Tord is searching through old memories...
```

After inference:

Delete the message.

Requirements:

* never persist in conversation history,
* never be sent to the LLM,
* always cleanup after success or failure.

---

# Feedback Message Templates

Create reusable template storage.

Suggested structure:

```
data/

└── feedback/

    ├── default.json
    ├── fantasy.json
    ├── sci-fi.json
    └── characters/

        ├── tord.json
        └── default.json
```

---

# Template Rendering

Support placeholders:

Required:

```
{{char}}
{{user}}
```

Future:

```
{{world}}
{{location}}
{{mood}}
```

Example:

```json
[
    "{{char}} is thinking...",
    "{{char}} is deciding what to tell {{user}}...",
    "{{char}} is searching memories..."
]
```

Rendered:

```
Tord is deciding what to tell Pablo...
```

---

# Message Selection Priority

Selection order:

```
Character-specific messages

        ↓

World-specific messages

        ↓

Generic messages
```

Example:

```
characters/tord.json

        ↓ fallback

default.json
```

---

# Repetition Prevention

Avoid showing the same messages repeatedly.

Implementation:

* keep a recent selection history,
* exclude recently used messages,
* reset when the pool is exhausted.

Example:

```
Pool:
50 messages

Recent:
message 5
message 12
message 31

Do not select these.
```

---

# Configuration

Example:

```json
{
    "processing_feedback_enabled": true,
    "typing_indicator_enabled": true,
    "temporary_messages_enabled": true,
    "delete_temporary_messages": true,
    "typing_refresh_seconds": 4
}
```

---

# Error Handling

Feedback must always stop.

Example:

```python
await feedback.start()

try:
    response = await generate()

finally:
    await feedback.stop()
```

Cases:

* successful generation,
* LLM failure,
* timeout,
* cancelled request.

The adapter must never leave:

* a permanent temporary message,
* a running typing task.

---

# Testing

## Port tests

Verify:

* start called,
* update called,
* stop called,
* cleanup happens on exceptions.

---

## Telegram adapter tests

Verify:

* typing action is sent,
* typing refresh loop stops,
* temporary message is created,
* temporary message is deleted.

---

# Future Extensions

## Progressive status updates

Example:

```
Searching memories...

Building response...

Writing reply...
```

These can map to real pipeline stages.

---

## Streaming responses

The same port could support:

```
start()

update("Generating response...")

update("Almost finished...")

stop()
```

---

## Mood-aware feedback

Use character state:

```
{{char}} is annoyed while thinking...
{{char}} is excited to answer...
```

---

## Multi-client support

Possible implementations:

```
Telegram:
    typing + temporary message

Discord:
    typing event + status message

Web:
    spinner + streaming state

Voice:
    "thinking" audio cue
```

---

### generic thinking message example

[
    "Consulting ancient tomes...",
    "Bribing the narrator...",
    "Rolling for intelligence...",
    "Trying not to hallucinate...",
    "Feeding the kobolds...",
    "Looking dramatically into the distance...",
    "Negotiating with the plot...",
    "Untangling the timeline...",
    "Convincing Tord this is a good idea...",
    "Searching memory crystals...",
    "Dusting off forgotten lore...",
    "Checking whether the dragon approves...",
]

### template based thinking message examples
[
  "{{char}} is thinking...",
  "{{char}} is looking at {{user}} thoughtfully...",
  "{{char}} is choosing the right words...",
  "{{char}} is remembering something...",
  "{{char}} is searching through old memories...",
  "{{char}} is deciding what to say next...",
  "{{char}} is trying not to blush...",
  "{{char}} is pretending to have everything under control...",
  "{{char}} is consulting the narrator...",
  "{{char}} is rolling for charisma...",
  "{{char}} is wondering what {{user}} is planning...",
  "{{char}} is checking whether this is a good idea...",
  "{{char}} is staring dramatically into the distance...",
  "{{char}} is definitely not making this up..."
]

---

# Completion Criteria

* [ ] Processing Feedback port exists
* [ ] Application layer uses the port
* [ ] Telegram adapter implements the port
* [ ] RP engine has no transport dependency
* [ ] Typing indicator works
* [ ] Temporary messages work
* [ ] Templates support {{char}} and {{user}}
* [ ] Character-specific feedback works
* [ ] Message repetition is controlled
* [ ] Cleanup works on errors
* [ ] Tests cover lifecycle behavior

