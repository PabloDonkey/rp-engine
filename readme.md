# RP Engine - Local Roleplay with Persistent Memory

A sophisticated local roleplay engine in Python that uses LM Studio (OpenAI-compatible API) as the backend LLM. Features persistent session memory, character state tracking, world state management, and intelligent prompt orchestration.

## Features (MVP)

✅ **Persistent Session Memory** - Full message history stored as JSON  
✅ **Character State Tracking** - Personality, tone, relationship levels  
✅ **World State Tracking** - Events, locations, status flags  
✅ **Prompt Orchestration** - Structured prompt building with system instructions  
✅ **CLI Interface** - Interactive chat loop with session management  
✅ **Type Safety** - Full Python type hints (mypy compatible)  
✅ **Code Quality** - Configured with ruff and mypy  
✅ **CI/CD** - GitHub Actions workflow for lint + type check + tests  

## Project Structure

```
rp-engine/
├── app/
│   ├── main.py                  # CLI entry point
│   ├── config.py                # Configuration management
│   └── __init__.py
│
├── llm/
│   ├── client.py                # LM Studio API wrapper (type-safe)
│   └── __init__.py
│
├── memory/
│   ├── session.py               # Session memory + persistence
│   ├── character.py             # Character state (personality, relationships)
│   ├── world.py                 # World state (events, flags, locations)
│   ├── compressor.py            # Memory compression (placeholder)
│   ├── store.py                 # JSON file storage utilities
│   └── __init__.py
│
├── engine/
│   ├── orchestrator.py          # Main orchestration engine
│   ├── prompt_builder.py        # Structured prompt building
│   └── __init__.py
│
├── data/
│   ├── sessions/                # Session JSON files
│   ├── worlds/                  # World state JSON files
│   └── characters/              # Character state JSON files
│
├── tests/                        # Test suite
├── .github/workflows/            # GitHub Actions CI
├── pyproject.toml              # Dependencies + tool config
├── .env.example                # Environment variables template
├── .python-version             # Python 3.12
└── README.md
```

## Quick Start

### Prerequisites

- **Python 3.12+**
- **LM Studio** running locally on `http://localhost:1234/v1`
- **pip** (Python package manager)

### Installation

1. **Navigate to the project:**
   ```bash
   cd /home/pablo/projects/rp-engine
   ```

2. **Run setup script:**
   ```bash
   bash setup.sh
   ```
   
   This creates a `.venv` wrapper and installs all dependencies.

3. **Verify setup:**
   ```bash
   bash verify.sh
   ```

### Running the Engine

**Option 1: Using .venv wrapper directly**
```bash
.venv/bin/python app/main.py
```

**Option 2: Using system Python directly**
```bash
python3.12 app/main.py
```

**Option 3: Activate venv in terminal and run**
```bash
source .venv/bin/activate
python app/main.py
deactivate  # when done
```

### Example Session

```
Session ID (or 'new' for new session): new
Enter new session ID: dragon_tavern
Character name: Aldric
Character personality for Aldric: Experienced tavern keeper, cynical but kind-hearted
Character tone (optional): Warm but sarcastic

Initializing LM Studio client...
API URL: http://localhost:1234/v1
============================================================
Session: dragon_tavern | Character: Aldric | Messages: 0
============================================================
Type 'exit' to quit, 'save' to save session, 'quit' to save and exit

> You walk into a quiet tavern and sit at the bar

Aldric glances up from polishing a glass, his weathered face breaking 
into a knowing smile. "Another soul seeking refuge from the world," he 
says, setting down the glass. "What can I get you?"

> save
Session saved.
```

### Example Session

```
============================================================
RP Engine - Local Roleplay with Persistent Memory
============================================================

Session ID (or 'new' for new session): new
Enter new session ID: dragon_tavern
Character name: Aldric
Character personality for Aldric: Experienced tavern keeper, cynical but kind-hearted
Character tone (optional): Warm but sarcastic

Initializing LM Studio client...
API URL: http://localhost:1234/v1
============================================================
Session: dragon_tavern | Character: Aldric | Messages: 0
============================================================
Type 'exit' to quit, 'save' to save session, 'quit' to save and exit

> You walk into a quiet tavern and sit at the bar

Aldric glances up from polishing a glass, his weathered face breaking 
into a knowing smile. "Another soul seeking refuge from the world," he 
says, setting down the glass. "What can I get you?"

> save
Session saved.
```

## Development

### Type Checking

```bash
mypy . --show-error-codes
```

### Linting

```bash
ruff check . --show-fixes
```

### Run Tests

```bash
pytest --cov=. --cov-report=term-only
```

### CI/CD

GitHub Actions automatically runs linting, type checking, and tests on push/PR to `main` or `develop`.

## Architecture

### Core Components

**Orchestrator** (`engine/orchestrator.py`)
- Main event loop coordinator
- Manages LLM interactions
- Persists messages to session memory
- Responsible for the `step()` function: user input → LLM response

**PromptBuilder** (`engine/prompt_builder.py`)
- Constructs structured prompts for the LLM
- Injects character system prompt
- Includes world state context
- Appends recent conversation history
- Formats complete message list for API

**SessionMemory** (`memory/session.py`)
- Stores complete message history
- Pydantic model for type safety
- Loads/saves to JSON files
- Supports message filtering and retrieval

**LMStudioClient** (`llm/client.py`)
- Wrapper around LM Studio's OpenAI-compatible API
- Typed request/response models
- Handles API communication
- Full error handling

**CharacterState** & **WorldState** (`memory/character.py`, `memory/world.py`)
- Persistent character personality and relationship tracking
- World events, locations, and state flags
- Designed for expansion with evolution tracking

## Data Persistence

All state is stored as JSON files in the `data/` directory:

- **Sessions**: `data/sessions/{session_id}.json`
- **Characters**: `data/characters/{character_name}.json`
- **Worlds**: `data/worlds/{world_name}.json`

Example session file:
```json
{
  "session_id": "dragon_tavern",
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:45:00",
  "character_name": "Aldric",
  "world_name": "Tavern District",
  "messages": [
    {
      "role": "user",
      "content": "You walk into a quiet tavern...",
      "timestamp": "2026-06-20T14:30:15"
    },
    {
      "role": "assistant",
      "content": "Aldric glances up from polishing a glass...",
      "timestamp": "2026-06-20T14:30:22"
    }
  ]
}
```

## Future Enhancements (Placeholders)

### Phase 2 - Memory Compression
- LLM-based summarization of old messages
- Automatic session compression when token count exceeds threshold
- State extraction: emotions, relationship changes, important facts

### Phase 3 - Character Evolution
- Track relationship evolution over sessions
- Personality shifts based on interactions
- Dialogue pattern learning

### Phase 4 - World Evolution
- Dynamic event generation
- State flag tracking and reactions
- Location descriptions that evolve

### Phase 5 - Advanced Features
- Multi-character conversations
- Conflict resolution engine
- Save/load snapshots
- Session branching/replay
- Export to markdown

## Environment Variables

See `.env.example`:

```env
# LM Studio API endpoint
LM_STUDIO_API_URL=http://localhost:1234/v1

# Data directory locations
SESSION_DIR=data/sessions
WORLDS_DIR=data/worlds
CHARACTERS_DIR=data/characters
```

## Configuration

Settings in `app/config.py`:
- LM Studio API URL (from env var)
- Data directory paths (from env vars)
- Auto-creates directories on startup

## Testing

Run the test suite:
```bash
pytest
```

With coverage:
```bash
pytest --cov=. --cov-report=html
```

## Troubleshooting

### LM Studio Connection Error
- Ensure LM Studio is running: `http://localhost:1234/v1`
- Check `LM_STUDIO_API_URL` in `.env`
- Verify a model is loaded in LM Studio

### Import Errors
- Ensure virtual environment is activated
- Run: `pip install -e ".[dev]"`
- Check Python 3.12+: `python --version`

### Type Checking Failures
- Run: `mypy . --show-error-codes`
- Most common: missing type hints on function parameters

## Code Quality Standards

- **Python 3.12** with full type hints
- **mypy** for static type checking (strict mode)
- **ruff** for linting and formatting
- **Pydantic** for data validation
- **pytest** for testing

All code must pass CI checks before merging.

## License

[Add license here]

## Author

Built as a local roleplay engine MVP with persistence and character tracking.
