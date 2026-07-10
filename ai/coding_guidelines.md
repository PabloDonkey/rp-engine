# Coding Guidelines

## Python

* Python version: 3.12+
* Use async by default for I/O operations
* Use type hints everywhere
* Prefer explicit code over clever abstractions

---

## Quality

All code must pass:

```
uv run ruff check .
uv run ruff format .
uv run mypy .
```

---

## Design

Follow:

* SOLID principles
* Dependency inversion
* Separation of concerns
* Composition over inheritance

Avoid:

* Global state
* Hidden dependencies
* Business logic in adapters
* Framework coupling in core

---

## Error Handling

* Fail gracefully
* Do not silently ignore errors
* Keep errors observable through logging

---

## Testing

New features should include tests.

Prefer:

* Unit tests for core logic
* Integration tests for adapters and external services
