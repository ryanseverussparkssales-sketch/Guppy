# Guppy — Personal AI Assistant System

A multi-agent AI system featuring **Guppy** (digital butler) and **Merlin** (Socratic mentor), running locally or via Claude API.

## Quick Start

### Installation

1. Clone or download this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. (Optional) Set your Anthropic API key for Claude mode:
   ```
   [System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","your-key-here","User")
   ```

### Running the Apps

**Windows:**
- **Guppy GUI:** Double-click `bin/launch_guppy.bat`
- **Merlin (Mentor):** Double-click `bin/launch_merlin.bat`
- **The Council** (both modes): Double-click `bin/launch_council.bat`

**Terminal:**
```
python guppy_ui.py      # GUI mode
python guppy_agent.py   # Terminal mode (with /web for browser interface)
python merlin_ui.py     # Merlin's study (spawned by Council)
```

## Architecture

### Entry Points
- **`guppy_ui.py`** – PySide6 GUI with push-to-talk voice, dark theme, AI orb indicator
- **`guppy_agent.py`** – Terminal REPL with Claude or Ollama backend, multiline input
- **`merlin_ui.py`** – Spellcaster interface with tool execution and ripple effects
- **`council_ui.py`** – Dual-window orchestrator (Guppy + Merlin conversation)

### Core Modules
- **`guppy_core.py`** – Shared system prompts, tool definitions, backend logic
- **`merlin_core.py`** – Spell toolkit (torrent search, research, task management, file ops)
- **`guppy_voice.py`** – Push-to-talk (sounddevice + Google Speech Recognition), Windows TTS
- **`guppy_memory.py`** – SQLite session persistence for chat history

### Models
- **`Modelfile`** – Ollama config for Guppy local model (butler personality)
- **`Modelfile_Merlin`** – Ollama config for Merlin (Socratic tutor)

### Tests
- **`tests/test_ptt.py`** – Voice capture & transcription verification

## Features

### Guppy (Butler Mode)
- **Modes:** Claude (online w/ vision) or local Ollama model
- **Voice:** Push-to-talk recording, Google Speech Transcription, Windows TTS
- **Tools:** PC control (screenshot, mouse, keyboard), email drafting, Gmail, Kindle, reports
- **Memory:** Optional session-based chat persistence

### Merlin (Mentor Mode)
- **Personality:** Socratic questioning, dry wit, archaic phrasing
- **Spells:** Web research, torrent search/management, file I/O, task/notes, terminal commands
- **Backend:** Ollama local model (`merlin`)

### The Council
- Simultaneous dual-window chat between Guppy and Merlin
- Each with independent backends and tool sets
- Rich visual feedback (orbs, ripple effects, state indicators)

## Configuration

### Environment Variables
```
ANTHROPIC_API_KEY          # Claude API key (optional for Guppy GUI)
UTORRENT_HOST              # uTorrent WebUI host (localhost)
UTORRENT_PORT              # uTorrent WebUI port (8080)
UTORRENT_USER              # uTorrent WebUI user (admin)
UTORRENT_PASS              # uTorrent WebUI password
PLEX_URL                   # Plex media server URL
PLEX_TOKEN                 # Plex auth token
VPN_CLIENT                 # VPN client type (not yet implemented)
```

### Ollama Setup
1. Install Ollama from ollama.ai
2. Pull local personas:
   ```
   ollama pull guppy
   ollama pull merlin
   ```
3. Load custom models:
   ```
   ollama create guppy -f models/Modelfile
   ollama create merlin -f models/Modelfile_Merlin
   ```
4. Serve on localhost:11434 (Ollama default)

## Dependencies

| Package | Purpose |
|---------|---------|
| PySide6 | GUI framework |
| requests | HTTP client |
| beautifulsoup4 | Web scraping |
| anthropic | Claude API |
| sounddevice | Audio input |
| soundfile | WAV file I/O |
| SpeechRecognition | Speech-to-text (Google) |
| pyttsx3 | Text-to-speech (Windows native) |
| keyboard | Global hotkey detection (planned) |
| open-webui | Browser-based Ollama UI |

## Project Structure

```
Guppy/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── guppy_ui.py                 # Guppy GUI entry point
├── guppy_agent.py              # Guppy terminal REPL
├── merlin_ui.py                # Merlin UI entry point
├── council_ui.py               # Dual-window orchestrator
├── guppy_core.py               # Shared backend logic
├── merlin_core.py              # Merlin spell definitions
├── guppy_voice.py              # Push-to-talk system
├── guppy_memory.py             # Session persistence
├── media_tools.py              # Media/torrent helpers
├── debug_console.py            # Debugging utilities
│
├── bin/
│   ├── launch_guppy.bat        # Windows launcher (Guppy)
│   ├── launch_merlin.bat       # Windows launcher (Merlin)
│   └── launch_council.bat      # Windows launcher (Council)
│
├── models/
│   ├── Modelfile               # Ollama config (Guppy)
│   └── Modelfile_Merlin        # Ollama config (Merlin)
│
├── tests/
│   └── test_ptt.py             # Voice system test
│
├── docs/
│   ├── FEATURES.md             # Feature deep-dives
│   ├── VOICE.md                # Voice setup guide
│   ├── API.md                  # Tool API reference
│   └── TROUBLESHOOTING.md      # Common issues
│
├── data/
│   ├── guppy_memory.db         # SQLite session cache
│   └── webui_data/             # Open WebUI runtime
│
└── .venv/                      # Python virtual environment
```

## Voices & Personalities

### Guppy
- **Persona:** British butler, dry wit, TARS-level directness
- **TTS Voice:** en-GB-RyanNeural (approx. Tim Curry)
- **Orb Color (Idle):** Deep indigo
- **Orb Color (Thinking):** Amber
- **Sign-off:** 🎩

### Merlin
- **Persona:** Ancient wizard, Socratic mentor, archaically witty
- **TTS Voice:** en-GB-ThomasNeural or en-IE-ConnorNeural
- **Orb Color (Idle):** Deep indigo
- **Orb Color (Thinking):** Amber
- **Sign-off:** ✦

## Troubleshooting

### No Sound in PTT
- Verify microphone in Windows Sound settings
- Run `tests/test_ptt.py` to diagnose
- Ensure sounddevice, soundfile, SpeechRecognition are installed

### Claude Mode Not Activating
- Check `ANTHROPIC_API_KEY` is set (use PowerShell `$env:ANTHROPIC_API_KEY`)
- Verify internet connection
- Check API key validity at console startup (watch for "Claude mode" message)

### Ollama Connection Failed
- Ensure Ollama is running: `ollama serve` in terminal
- Verify localhost:11434 is reachable: `curl http://localhost:11434/api/tags`
- Pull local personas: `ollama pull guppy` and `ollama pull merlin`

### Voice Transcription Errors
- "Could not understand audio" → Speak more clearly or reduce background noise
- Network timeout → Google Speech Recognition requires internet
- Device error → Check microphone selection in `guppy_voice.py` VoiceConfig

## Development

### Adding a New Tool
1. Define in `guppy_core.py` (TOOLS list)
2. Implement in `guppy_core.py` (run_tool function)
3. For Merlin, add alias in `merlin_core.py` (SPELL_MAP)

### Extending the UI
- `guppy_ui.py` uses PySide6 and custom gradients/animations
- Orb state machine: "idle", "thinking", "listening", "speaking"
- Chat bubbles auto-scroll to latest message

### Custom Prompts
- Edit `SYSTEM` prompt in `guppy_core.py` or `MERLIN_SYSTEM` in `merlin_core.py`
- Rebuild Ollama models: `ollama create guppy -f models/Modelfile`

## License

Personal project. Modify as needed.

## Credits

- **Ollama** – Local LLM engine (ollama.ai)
- **Anthropic** – Claude API (anthropic.com)
- **PySide6** – Cross-platform GUI framework
- **Google Speech Recognition** – STT service

---

**Master Ryan's Digital Assistant Suite** ✦🎩
