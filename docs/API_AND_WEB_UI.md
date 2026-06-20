# REST API & Web UI

The RP Engine now includes a REST API with a beautiful web interface for interactive roleplay without terminal limitations.

## Quick Start

**Start the API server:**
```bash
./run_api.sh
```

The server will start at `http://localhost:5000`

**Open in browser:**
```
http://localhost:5000
```

## Features

✅ **Multiline Text Support** - Type as much as you want, Shift+Enter for newlines
✅ **Easy Copy/Paste** - Full drag-and-drop support
✅ **Session Management** - Create, load, list all sessions
✅ **Character Control** - Manage character personality and relationships  
✅ **World Building** - Create and manage world settings
✅ **Clean UI** - Modern, responsive interface for all devices

## API Endpoints

### Sessions
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/{id}` - Get session details
- `POST /api/sessions/{id}/message` - Send message, get response

### Characters
- `GET /api/characters` - List all characters
- `POST /api/characters` - Create new character
- `GET /api/characters/{name}` - Get character details

### Worlds
- `GET /api/worlds` - List all worlds
- `POST /api/worlds` - Create new world
- `GET /api/worlds/{name}` - Get world details

### Health
- `GET /health` - API health check

## Example Usage (curl)

**Create a session:**
```bash
curl -X POST http://localhost:5000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "adventure",
    "character_name": "Wizard",
    "world_name": "Magic Forest"
  }'
```

**Send a message:**
```bash
curl -X POST http://localhost:5000/api/sessions/adventure/message \
  -H "Content-Type: application/json" \
  -d '{"content": "What do you see ahead?"}'
```

**List sessions:**
```bash
curl http://localhost:5000/api/sessions
```

## Architecture

```
┌─────────────────────────────────────────┐
│      Web Browser (HTML/JS)              │
│   (app/static/index.html)               │
└────────────────┬────────────────────────┘
                 │ HTTP REST API
                 ↓
┌─────────────────────────────────────────┐
│  Flask REST Server (app/api.py)         │
│  - Session management                   │
│  - Character management                 │
│  - World management                     │
│  - Message routing                      │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ↓                     ↓
  ┌─────────┐          ┌──────────┐
  │ Local   │          │   LM     │
  │ JSON    │          │  Studio  │
  │Storage  │          │  (LLM)   │
  └─────────┘          └──────────┘
```

## Configuration

Edit `.env` to customize:
```
API_PORT=5000
LM_STUDIO_API_URL=http://localhost:1234/v1
SESSION_DIR=data/sessions
WORLDS_DIR=data/worlds
CHARACTERS_DIR=data/characters
```

## Comparing CLI vs Web UI

| Feature | CLI | Web UI |
|---------|-----|-------|
| Multiline Input | ❌ Limited | ✅ Full support |
| Copy/Paste | ⚠️ Terminal dependent | ✅ Works perfectly |
| Session Management | ✅ Manual | ✅ Auto-save |
| User Interface | 🖥️ Text-based | 🎨 Modern & Beautiful |
| Remote Access | ❌ No | ✅ Local network |
| Scriptable (curl) | ❌ No | ✅ Yes |
| AI Agents (calls API) | ❌ No | ✅ Yes |

## Why Choose Each?

**Use CLI (`./run.sh`) when:**
- You're a power user comfortable with terminal
- You want direct orchestrator control
- Testing system behavior

**Use Web UI (`./run_api.sh`) when:**
- You want a better user experience
- You need multiline input
- You're integrating with other tools
- You want to script interactions with curl
- You need a clean, modern interface
