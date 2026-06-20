# ⚡ Quick Start (2 minutes)

## Prerequisites
- **Python 3.12** installed: `python3.12 --version`
- **LM Studio** running on `http://localhost:1234/v1` with a model loaded

## Setup (one-time)

```bash
cd /home/pablo/projects/rp-engine

# Run setup script to create .venv and install dependencies
bash setup.sh
```

This will:
- ✅ Create Python virtual environment (.venv)
- ✅ Install dependencies
- ✅ Create `.env` file

## Run the Engine

### Option 1: Activate venv first
```bash
source .venv/bin/activate
python app/main.py
```

### Option 2: Run directly
```bash
.venv/bin/python app/main.py
```

## Example Session

```
Session ID (or 'new' for new session): new
Enter new session ID: tavern_night
Character name: Bartender
Character personality for Bartender: Gruff but generous, seen it all
Character tone (optional): Warm and sarcastic

Initializing LM Studio client...
API URL: http://localhost:1234/v1
============================================================
Session: tavern_night | Character: Bartender | Messages: 0
============================================================
Type 'exit' to quit, 'save' to save session, 'quit' to save and exit

> You walk through the tavern door

The bartender looks up and nods...
[Model response here]

> Type more messages or 'quit' to save and exit
```

## Verify Installation

```bash
bash verify.sh
```

## Troubleshooting

**Error: "Connection refused" or LM Studio error**
- Make sure LM Studio is running on `http://localhost:1234/v1`
- Check that a model is loaded in LM Studio

**Error: "ModuleNotFoundError"**
- Activate venv: `source .venv/bin/activate`
- Or run setup again: `bash setup.sh`
- Make sure Python 3.12 is installed

**Error: "Python 3.12 not found"**
- Install Python 3.12 or check your PATH
- Use `python3.12 --version` to verify

**Error: "venv/bin/activate: No such file or directory"**
- Run setup script: `bash setup.sh`
- This creates the .venv directory and activates it

## Commands in Chat

- Type normally to chat
- `save` - Save the session without exiting
- `quit` - Save and exit
- `exit` - Exit without saving (loses this session!)
- `Ctrl+C` - Emergency exit (auto-saves)

## Data Persistence

All sessions, characters, and worlds are saved as JSON files in:
- `data/sessions/` - Conversation history
- `data/characters/` - Character personality & relationship
- `data/worlds/` - World state & events

## Using the Virtual Environment

**In current terminal (after running setup.sh):**
```bash
source .venv/bin/activate  # Activate venv
python app/main.py         # Run app
deactivate                 # Deactivate venv when done
```

**In a new terminal:**
```bash
cd /home/pablo/projects/rp-engine
source .venv/bin/activate
python app/main.py
```

**Without activating (direct path):**
```bash
.venv/bin/python app/main.py
```

## Next Steps

- ✅ Read [README.md](README.md) for full documentation
- 📖 Check [DEVELOPMENT.md](DEVELOPMENT.md) for code quality
- 🔧 Look at future enhancements in README.md

---

**Having issues?** Check the [Troubleshooting section](README.md#troubleshooting) in README.md
