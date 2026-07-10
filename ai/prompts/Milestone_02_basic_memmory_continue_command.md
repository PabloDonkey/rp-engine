# Milestone 2 Corrections — Memory Ownership and Continue Command

Apply these corrections to the Milestone 2 implementation.

---

## Memory Ownership

Keep the first implementation intentionally simple.

Do not introduce session management yet.

Memory is attached to:

* Telegram user_id for private chats
* Telegram group_id for group chats

The memory key should be derived from the external conversation identity.

Example:

```text
private chat:
memory_key = user_id

group chat:
memory_key = group_id
```

The abstraction should allow future evolution toward:

```text
user_id
    |
    +-- session_id
          |
          +-- memory
```

but session switching is not part of this milestone.

---

## Memory Storage

Use JSON files.

Example:

```text
data/
└── memory/
    ├── user_12345.json
    └── group_-98765.json
```

Each memory file stores only conversation history:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I enter the forest"
    },
    {
      "role": "assistant",
      "content": "The trees whisper around you"
    }
  ]
}
```

---

## Continue Command Behavior

The `/continue` command is not a normal user message.

Do not store:

```text
/continue
```

in memory.

Do not store:

```text
Continue the narration naturally from the current context.
```

in memory.

The continuation instruction is temporary generation metadata.

---

## Continue Flow

When receiving:

```text
/continue
```

The system should:

1. Resolve the current memory owner.
2. Load previous conversation history.
3. Add a temporary instruction for generation.
4. Call the LLM.
5. Store only the assistant response.

Example internal flow:

```text
Telegram:
/continue

        ↓

ChatService

        ↓

Load memory

        ↓

Generate with continuation intent

        ↓

Save assistant response only
```

---

## Future Compatibility

Design the APIs so session support can be added later.

Avoid naming everything "session".

Prefer concepts like:

```python
MemoryKey
ConversationIdentity
MemoryOwner
```

A future command like:

```text
/session fantasy
```

may later switch the active memory namespace.
