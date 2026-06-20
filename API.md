# RP Engine - Backend API

The core roleplay engine with session management, character memory, and LLM orchestration.

## Running the API Server

```bash
python -m app.api
```

The API will start on `http://localhost:5000` by default.

### Environment Variables

- `LM_STUDIO_API_URL`: LM Studio API endpoint (default: `http://localhost:1234/v1`)
- `API_PORT`: Port to run the API server (default: `5000`)
- `SESSION_DIR`: Directory for session data (default: `data/sessions`)
- `CHARACTERS_DIR`: Directory for character data (default: `data/characters`)
- `WORLDS_DIR`: Directory for world data (default: `data/worlds`)

## API Endpoints

### Health
- `GET /health` - Health check

### Sessions
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create a new session
- `GET /api/sessions/<id>` - Get session details
- `DELETE /api/sessions/<id>` - Delete a session
- `POST /api/sessions/<id>/message` - Send a message and get LLM response

### Characters
- `GET /api/characters` - List all characters
- `POST /api/characters` - Create a new character
- `GET /api/characters/<name>` - Get character details
- `PUT /api/characters/<name>` - Update a character
- `DELETE /api/characters/<name>` - Delete a character

### Worlds
- `GET /api/worlds` - List all worlds
- `POST /api/worlds` - Create a new world
- `GET /api/worlds/<name>` - Get world details
- `DELETE /api/worlds/<name>` - Delete a world

## Architecture

- **engine/**: Core orchestration and prompt building
- **memory/**: Character, session, and world memory management
- **llm/**: LM Studio client integration
- **app/**: Flask API server

See the main [README.md](../readme.md) for more information.
