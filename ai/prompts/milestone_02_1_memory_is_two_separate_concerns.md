# Milestone 2 Architecture Clarification — Memory Is Two Separate Concerns

Before implementing Milestone 2, revise the memory design understanding.

The goal is not only to add JSON memory.

The goal is to establish the correct abstraction boundary for future interchangeable memory systems.

---

## Memory has two separate responsibilities

Do not combine these concepts.

---

# 1. Conversation Storage

Responsibility:

Where conversation data is stored.

Examples:

```text id="mx4j7t"
JsonConversationStore
SQLiteConversationStore
VectorConversationStore
```

Operations:

```python
save_message()
load_messages()
clear()
```

The store does not decide:

* what memories matter
* what context goes to the LLM
* summarization
* relevance

---

# 2. Memory Strategy

Responsibility:

How stored conversation history is transformed into LLM context.

Examples:

```text id="z6m4z0"
DumpEverythingStrategy
SlidingWindowStrategy
SummaryStrategy
RetrievalStrategy
HybridStrategy
```

The strategy receives conversation history and returns the context to use.

Example:

```text id="d5pk3s"
ConversationStore

1000 messages

        ↓

MemoryStrategy

last 20 messages
+ summary
+ relevant memories

        ↓

PromptBuilder

LLM context
```

---

# Milestone 2 Scope

Implement only:

## Storage

```text id="w2y0i8"
JsonConversationStore
```

## Strategy

```text id="frz1wo"
DumpEverythingStrategy
```

The strategy should simply return all available messages.

No summarization.
No retrieval.
No embeddings.

---

# Desired dependency direction

```text id="u6v5b9"
core

    ports/
        conversation_store.py
        memory_strategy.py


infrastructure/

    storage/
        json_conversation_store.py
```

The core defines interfaces.

Infrastructure implements storage.

---

# Chat Flow

The flow should become:

```text id="u9g98a"
Incoming message

        ↓

Conversation identity

        ↓

ConversationStore.load()

        ↓

MemoryStrategy.build_context()

        ↓

PromptBuilder

        ↓

LLM

        ↓

ConversationStore.save()
```

---

# Important

Do not create a generic "MemoryManager" that owns everything.

Avoid coupling:

* storage
* context selection
* summarization
* retrieval

These must remain replaceable independently.

---

Proceed with the smallest implementation that creates these boundaries.
