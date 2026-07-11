# Milestone 2C — Telegram Message Splitting

Before making changes, read:

* README.md
* docs/ARCHITECTURE.md
* docs/SPEC.md
* ai/project_context.md
* ai/coding_guidelines.md
* ai/implementation_rules.md

The RP Engine now generates complete responses.

Telegram has a maximum message size.

This limitation belongs entirely to the Telegram adapter.

Do not move any message splitting logic into the core.

---

# Objective

Implement intelligent Telegram message splitting.

The core returns one complete string.

The Telegram adapter is responsible for delivering that response as one or more Telegram messages.

---

# Architecture

The desired flow is:

```text
LLM
    │
    ▼
Complete response
    │
    ▼
ChatService
    │
    ▼
Telegram Adapter
    │
    ▼
Message Splitter
    │
    ├── chunk 1
    ├── chunk 2
    ├── chunk 3
    ▼
Telegram API
```

The RP engine must never know that Telegram limits message size.

---

# New Component

Create:

```text
src/rp_engine/adapters/telegram/splitter.py
```

Expose one public function similar to:

```python
split_message(
    text: str,
    max_length: int,
) -> list[str]
```

Keep it completely independent from Telegram APIs so it is easy to unit test.

---

# Maximum Size

Do not use Telegram's absolute maximum.

Introduce a configurable safe limit.

Default:

```python
3800
```

Leave a safety margin below Telegram's limit.

---

# Splitting Algorithm

The goal is readability.

Never simply split every N characters.

Prefer the following order.

## Priority 1

Split between paragraphs.

```text
Paragraph 1

Paragraph 2
```

---

## Priority 2

Split on newline.

```text
Line 1
Line 2
```

---

## Priority 3

Split after sentence-ending punctuation.

Prefer:

* .
* !
* ?
* …
* : (when appropriate)

Keep punctuation attached to the sentence.

---

## Priority 4

Split on whitespace.

Never split in the middle of a word if it can be avoided.

---

## Priority 5

Only as a last resort:

Split at the maximum length.

This should be extremely rare.

---

# Preserve Formatting

Do not remove:

* blank lines
* markdown
* indentation
* bullet lists
* quoted text

Chunks should reconstruct the original message exactly when concatenated.

---

# Edge Cases

Support:

Very large paragraphs

Very long code blocks

Large markdown lists

Single words longer than the limit

Unicode

Emoji

Multiple blank lines

Trailing whitespace

---

# Delivery

The Telegram adapter should automatically send every chunk.

Example:

```python
chunks = split_message(reply)

for chunk in chunks:
    await send_message(chunk)
```

No special handling is required by the caller.

---

# Logging

When debug logging is enabled, log:

```text
Telegram Message

Characters:
8427

Chunks:
3

Chunk sizes:
3792
3788
847
```

Do not log message contents.

Only statistics.

---

# Tests

Create comprehensive tests.

Verify:

Short messages produce one chunk.

Paragraph boundaries are preferred.

Sentence boundaries are preferred.

Words are not split unnecessarily.

Formatting is preserved.

Concatenating all chunks recreates the original message exactly.

No chunk exceeds the configured maximum.

Unicode and emoji remain intact.

Extremely long words are handled safely.

---

# Documentation

Update ARCHITECTURE.md.

Document:

Telegram message splitting is a transport concern.

The RP engine always returns one complete response.

Adapters are responsible for platform delivery constraints.

---

# ADR-016 — Transport Adapters Handle Message Size Limits

Decision:

Platform-specific output limitations (Telegram maximum message size, Discord limits, etc.) belong to adapters.

The core engine always produces a complete response and remains unaware of transport constraints.

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
* test coverage
* assumptions made

If a tradeoff is required, explain it before implementation.
