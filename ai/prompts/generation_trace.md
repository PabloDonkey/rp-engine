# Decision — Add Generation Trace Logging

## Context

The RP Engine currently persists the canonical conversation (`history.jsonl`) and the current session state (`session.json`).

While this is sufficient for restoring conversations and maintaining memory, it is insufficient for debugging LLM behavior. When a response is incorrect (for example, ignoring the latest user input, breaking character, or producing an unexpected monologue), there is no way to determine whether the issue originated from:

* Prompt assembly
* Memory retrieval
* Character or world state injection
* Conversation history formatting
* Provider configuration
* Generation parameters
* The LLM itself

Reproducing these issues after the fact is difficult because the exact prompt sent to the model is lost.

---

## Decision

Introduce an optional **Generation Trace** feature.

A Generation Trace records every completed LLM inference as a structured JSON object written to `trace.jsonl`.

The trace is **diagnostic only**.

It is **not** part of the RP domain model and **must never** be used for memory retrieval, prompt construction, conversation replay, or any runtime logic.

Its sole purpose is observability, debugging, testing, and performance analysis.

---

## Directory Layout

Example:

```text
data/
└── sessions/
    └── <session_id>/
        ├── history.jsonl
        ├── session.json
        └── trace.jsonl
```

---

## Trace Record

Each line of `trace.jsonl` represents one completed inference.

Suggested structure:

```json
{
  "timestamp": "...",
  "turn": 21,
  "request_id": "...",

  "provider": "lmstudio",
  "model": "qwen3-30b",

  "prompt": {
    "character": "...",
    "world": "...",
    "memory": "...",
    "conversation_rules": "...",
    "assembled_system_prompt": "..."
  },

  "messages": [
    ...
  ],

  "generation": {
    "temperature": 0.8,
    "top_p": 0.95,
    "max_tokens": 400,
    "seed": 42
  },

  "response": "...",

  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 214
  },

  "finish_reason": "stop",

  "latency_ms": 1843
}
```

The exact schema may evolve, but every record must be self-contained enough to understand and reproduce a single generation.

---

## Logging Requirements

The trace should include, when available:

* Timestamp
* Turn number
* Request ID
* Provider
* Model
* Prompt sections before assembly
* Final assembled system prompt
* Complete message list sent to the provider
* Generation parameters
* Assistant response
* Token usage
* Finish reason
* Latency

Provider-specific metadata may also be recorded when available.

---

## Design Principles

### Read-only

Trace files are never read by the engine during runtime.

They are write-only diagnostic artifacts.

---

### Append-only

Each inference appends a single JSON object.

Existing records are never modified.

---

### Independent

The trace system must not influence generation.

Disabling tracing must not change engine behavior.

---

### Provider-agnostic

The feature belongs to the application/infrastructure layer.

It should work with any future LLM provider without coupling to LM Studio.

---

### Human-readable

The trace should be easy to inspect manually.

JSON Lines is preferred because it supports:

* streaming writes
* large files
* command-line tools
* external analysis

---

## Configuration

Tracing should be configurable.

Suggested configuration:

```yaml
debug:
  generation_trace: off | errors | all
```

Behavior:

* **off** — no traces are written.
* **errors** — write traces only for failed requests or failed post-generation validation.
* **all** — trace every inference.

---

## Future Extensions

The trace format should allow optional sections without breaking compatibility.

Possible future additions include:

* Memory retrieval diagnostics
* Retrieved documents
* Prompt token allocation
* Judge evaluation
* Safety checks
* Response rewriting history
* Streaming statistics
* Cost estimation
* Provider raw response

These additions should remain optional and should not require changes to the existing runtime architecture.

---

## Consequences

### Positive

* Greatly improves reproducibility of generation issues.
* Makes prompt engineering significantly easier.
* Enables regression testing using real prompts.
* Simplifies bug reports.
* Allows detailed performance analysis.
* Provides a foundation for future LLM Judge integration.

### Negative

* Increased disk usage.
* Trace files may contain duplicated prompt data.
* Prompt contents may include sensitive user information and should be treated with the same privacy guarantees as conversation history.

---

## Out of Scope

This feature does **not**:

* Replace `history.jsonl`.
* Replace `session.json`.
* Affect memory retrieval.
* Modify prompt generation.
* Replay conversations.
* Implement response judging.
* Implement analytics.

It is strictly an observability and debugging feature.
