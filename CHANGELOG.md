# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-20 - MVP Release

### Added

#### Core Infrastructure
- Complete project structure with clean module separation
- `app/config.py` - Configuration management with environment variables
- `pyproject.toml` - Python 3.12 project configuration with Pydantic, requests, python-dotenv
- Type safety with mypy strict mode compliance
- Code quality with ruff linting

#### LLM Integration
- `llm/client.py` - LM Studio API client with OpenAI-compatible endpoint
- Full Pydantic models for request/response validation:
  - `ChatMessage`, `ChatCompletionRequest`, `ChatCompletionResponse`
- Proper error handling and status code checking

#### Memory Management
- `memory/session.py` - SessionMemory model with persistent storage
  - Full message history with timestamps
  - SessionManager for load/save operations
  - Supports retrieval of recent messages
- `memory/character.py` - CharacterState with personality tracking
  - Relationship level tracking (-100 to +100)
  - Character persistence via JSON
  - CharacterManager for lifecycle management
- `memory/world.py` - WorldState for environment tracking
  - Event logging system
  - State flags (flexible dict-based storage)
  - World persistence
  - WorldManager for management
- `memory/store.py` - JSON persistence utilities
- `memory/compressor.py` - Memory compression placeholder
  - Token estimation
  - Compression detection
  - Future LLM-based summarization ready

#### Engine & Orchestration
- `engine/prompt_builder.py` - PromptBuilder for structured prompts
  - System prompt injection with character context
  - World state inclusion
  - Recent conversation history inclusion
  - Message formatting for API calls
- `engine/orchestrator.py` - Main orchestrator
  - Coordinates LLM, sessions, characters, worlds
  - `step()` method for user→model→memory flow
  - Session summary generation

#### CLI Interface
- `app/main.py` - Interactive chat CLI
  - Session creation/loading
  - Character setup and loading
  - World initialization
  - Interactive chat loop
  - Commands: save, quit, exit
  - Graceful error handling
  - Auto-save on Ctrl+C

#### Testing & Quality Assurance
- `tests/test_models.py` - Comprehensive unit tests
  - Message model tests
  - SessionMemory tests
  - CharacterState tests
  - WorldState tests
- `.github/workflows/ci.yml` - GitHub Actions CI pipeline
  - ruff linting checks
  - mypy type checking
  - pytest test runner
  - Runs on push/PR to main and develop

#### Documentation
- `README.md` - Comprehensive documentation
  - Feature list
  - Project structure
  - Quick start guide
  - Architecture overview
  - Development instructions
  - Troubleshooting guide
- `QUICKSTART.md` - Fast 2-minute setup guide
- `DEVELOPMENT.md` - Development and code quality guidelines
- `CHANGELOG.md` - This file

#### Setup & Deployment
- `setup.sh` - Automated setup script
  - Creates virtual environment
  - Installs dependencies
  - Creates .env file
- `verify.sh` - Setup verification script
  - Checks Python version
  - Verifies file structure
  - Validates installation
- `.env.example` - Environment configuration template
- `.python-version` - Python 3.12 specification
- `.gitignore` - Proper Python project ignore rules

### Architecture Highlights

#### Type Safety
- All modules use full type hints
- mypy strict mode compliance
- Pydantic models for data validation
- No untyped boundaries

#### Modular Design
- Clear separation of concerns
- Managers handle persistence
- Models handle data representation
- Orchestrator handles coordination
- Builders handle prompt construction

#### Extensibility
- Placeholder implementations for future phases:
  - LLM-based memory compression
  - Character evolution tracking
  - World state evolution
  - Multi-character support

### Data Persistence

- Sessions: `data/sessions/{session_id}.json`
- Characters: `data/characters/{character_name}.json`
- Worlds: `data/worlds/{world_name}.json`
- All stored as pretty-printed JSON for readability

### Code Quality Standards

- ✅ Python 3.12 target
- ✅ Full type hints on all functions
- ✅ mypy strict mode compliant
- ✅ ruff linting configured
- ✅ Pydantic for validation
- ✅ Docstrings on all classes/methods
- ✅ pytest test suite with coverage

### Known Limitations

- Memory compression not yet implemented (placeholder only)
- Single character per session (multi-character support planned)
- No API server yet (CLI only)
- No session branching/replay
- No world evolution triggers

### Future Roadmap

#### Phase 2 - Memory Compression
- LLM-based summarization of old messages
- Automatic compression when token count exceeds threshold
- State extraction and consolidation

#### Phase 3 - Character Evolution
- Track relationship changes over time
- Personality shifts based on interactions
- Dialogue pattern learning

#### Phase 4 - World Evolution
- Dynamic event generation
- State-triggered reactions
- Environmental storytelling

#### Phase 5 - Advanced Features
- Multi-character conversations
- Conflict resolution engine
- Session snapshots and branching
- Export to markdown
- Web UI

### Dependencies

**Runtime:**
- pydantic>=2.0.0 - Data validation
- requests>=2.31.0 - HTTP client for LM Studio
- python-dotenv>=1.0.0 - Environment configuration

**Development:**
- mypy>=1.8.0 - Static type checking
- ruff>=0.2.0 - Linting and formatting
- pytest>=7.4.0 - Testing framework
- pytest-cov>=4.1.0 - Coverage reporting

### Installation

```bash
bash setup.sh
source venv/bin/activate
python app/main.py
```

Requires LM Studio running on http://localhost:1234/v1

---

## [Unreleased]

### Planned for Next Release
- Memory compression implementation
- Character evolution system
- World event system
- API server (Flask/FastAPI)
- Web UI prototype
- Integration tests
- Performance benchmarks
