# Development Guide

## Code Quality

This project enforces strict code quality standards with **mypy** type checking and **ruff** linting.

### Run Type Checking

```bash
mypy . --show-error-codes
```

All functions must have:
- Parameter type hints
- Return type hints
- Docstrings

### Run Linting

```bash
ruff check . --show-fixes
```

Fix automatic issues:
```bash
ruff check . --fix
```

### Run Tests

```bash
pytest
```

With coverage report:
```bash
pytest --cov=. --cov-report=html
```

## Pre-commit Verification

Before committing, run all checks:

```bash
./run-checks.sh  # (if available, or run individually)
```

Or run manually:
```bash
mypy . --show-error-codes && \
ruff check . && \
pytest
```

## Project Structure Guidelines

### Adding a New Module

1. Create file in appropriate directory
2. Add docstring at top of file
3. Ensure all functions have type hints and docstrings
4. Add tests in `tests/`
5. Run checks before committing

### Type Hints Requirements

All functions must follow this pattern:

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    """
    # implementation
```

### Docstrings

Use Google-style docstrings:

```python
class MyClass:
    """Brief class description."""
    
    def my_method(self, arg: str) -> int:
        """Brief method description.
        
        Args:
            arg: Argument description
            
        Returns:
            Return value description
            
        Raises:
            ValueError: When value is invalid
        """
```

## CI/CD Pipeline

GitHub Actions automatically runs on push/PR:

1. **Lint** with ruff
2. **Type check** with mypy
3. **Test** with pytest

All checks must pass before merging to `main`.

## Common Issues

### mypy Strict Mode

Common errors and solutions:

```python
# ❌ Missing return type
def get_user():
    return user

# ✅ Fixed
def get_user() -> User:
    return user
```

```python
# ❌ Untyped parameter
def process(data):
    return data

# ✅ Fixed
def process(data: str) -> str:
    return data
```

### Pydantic Models

Always use Pydantic models for data validation:

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    name: str
    age: int = Field(gt=0, le=150)
```

## Development Workflow

1. Create a feature branch
2. Make changes
3. Run all checks: `mypy . && ruff check . && pytest`
4. Commit and push
5. GitHub Actions runs CI
6. Create PR when ready
7. All checks must pass before merge

## Debugging

### Enable verbose output

```bash
# Verbose mypy
mypy . --show-error-codes -v

# Verbose ruff
ruff check . --show-fixes --debug

# Verbose pytest
pytest -v
```

### Check type hints

Use reveal_type for debugging:

```python
from typing import reveal_type

reveal_type(my_variable)  # mypy will show the type
```

## Performance Notes

- Sessions store full message history (implement compression if > 100 messages)
- JSON files use pretty-printing (consider minification for production)
- Pydantic model validation is fast enough for interactive use

## Future Improvements

- Add integration tests
- Add performance benchmarks
- Implement memory compression
- Add API endpoint tests
