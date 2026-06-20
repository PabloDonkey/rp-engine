# Getting Started - Choose Your Interface

Your RP Engine is ready! You have two ways to use it. Pick one:

## 🌐 Web UI (Recommended - Better UX)

**Start the server:**
```bash
./run_api.sh
```

**Open in browser:**
```
http://localhost:5000
```

**Features:**
- ✨ Modern, beautiful interface
- 📝 Multiline text input (unlimited length)
- 📋 Full copy/paste support
- 💾 Auto-saves your session
- 📱 Works on mobile too
- 🔌 Any frontend can connect to the API

---

## 🖥️ CLI (Terminal - Direct Control)

**Start the CLI:**
```bash
.venv/bin/python app/main.py
```

**Features:**
- ⚡ Instant startup
- 🔧 Direct orchestrator control
- 💪 For power users
- 📊 See all internal state

---

## Choosing

| Need | Choose |
|------|--------|
| Best experience | **Web UI** ✨ |
| Multiline/paste | **Web UI** ✨ |
| Power user control | **CLI** 🖥️ |
| Testing with curl | **Web UI API** 🔌 |
| Quick startup | **CLI** 🖥️ |

---

## What You Need Running

Before starting either, ensure:

1. **LM Studio** running
   ```bash
   # On Windows: LM Studio app
   # On Linux/Mac: docker or native run
   # API should be at: http://localhost:1234/v1
   ```

2. **Check connection:**
   ```bash
   # If using Web UI, it auto-checks health
   # If using CLI, it tests on startup
   ```

---

## Troubleshooting

**"Cannot connect to LM Studio"**
- Make sure LM Studio is running and listening on port 1234
- Update `.env` if using different port: `LM_STUDIO_API_URL=http://localhost:1234/v1`

**"Port 5000 already in use"**
- Change API port in `.env`: `API_PORT=5001`

**"Module not found"**
- Run setup.sh: `bash setup.sh`
- Run verify.sh: `bash verify.sh`

---

## Next Steps

### Try the Web UI
1. Run `./run_api.sh`
2. Open http://localhost:5000
3. Click "Start" to create a session
4. Start typing (multiline works!)

### Try the CLI
1. Run `.venv/bin/python app/main.py`
2. Enter session ID when prompted
3. Follow the setup flow
4. Start chatting

### API Testing (curl)
See [API_AND_WEB_UI.md](docs/API_AND_WEB_UI.md) for examples

---

Happy roleplaying! 🎭
