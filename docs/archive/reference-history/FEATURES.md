# Features & Capabilities

## Guppy — Digital Butler

### GUI Interface (PySide6)
- **Dark theme** with cyan (#00c8ff) accents and gradient backgrounds
- **Animated orb** indicator: idle (indigo) → thinking (amber) → speaking (gold) → listening (cyan)
- **Chat bubbles** with speaker labels, color-coded by sender
- **Sidebar** with quick-action buttons (Gmail, Kindle, reports)
- **Mode toggle** (Claude ↔ local Ollama model)
- **Push-to-talk button** with visual feedback (listening state)

### Terminal Interface
- Interactive REPL with `/exit`, `/clear`, `/web`, `/mode` commands
- Multiline input (type `"""` on its own line)
- Live tool execution with preview output
- Optional memory briefing loaded at startup

### Personas
- **Guppy (Online/Claude):** British butler, dry wit, TARS-level directness
- **Guppy (Local/Ollama):** Same personality, running local `guppy` model
- **Merlin (Local/Ollama):** Socratic mentor, leads via questions, archaic phrasing

### Voice Features
- **Push-to-talk:** Record via sounddevice, transcribe via Google Speech Recognition
- **Text-to-speech:** Windows SAPI 5.1, configurable voices/rates/pitch
- **Auto-play:** Last assistant message spoken on completion

### AI Tools (Guppy)
| Tool | Function |
|------|----------|
| execute_command | Run PowerShell commands |
| screenshot | Capture screen (with base64 vision) |
| mouse_click / mouse_move | Control cursor |
| keyboard_type / keyboard_shortcut | Type text, press keys |
| read_file / write_file | File I/O |
| list_directory | Directory listing |
| open_application | Launch apps, URLs, files |
| open_gmail / draft_email | Email integration |
| open_kindle | Kindle store access |
| get_screen_info | Display info (resolution, cursor pos) |
| create_call_report | Generate call notes (save to Documents) |
| create_order_note | Generate order notes (save to Documents) |
| search_web | DuckDuckGo search |
| remember / recall / forget | Memory tome (SQLite) |
| add_task / get_tasks / complete_task | Task management |

### AI Tools (Merlin)
| Spell Name | Mapped Tool | Function |
|-----------|-------------|----------|
| scry | search_web | Quick web search |
| research | research | Deep research (URL fetch + DuckDuckGo) |
| inscribe | remember | Save fact to memory |
| commune | recall | Retrieve from memory |
| unbind | forget | Delete memory entry |
| bind_quest | add_task | Create task |
| read_scroll | get_tasks | View tasks |
| seal_quest | complete_task | Mark task done |
| invoke | execute_command | Run terminal command |
| unfurl | read_file | Read file |
| transcribe | write_file | Write file |
| survey | list_directory | List directory |
| seek_torrent | seek_torrent | Search torrents (YTS, 1337x) |
| summon_torrent | summon_torrent | Add torrent to uTorrent |
| view_torrents | view_torrents | List active torrents |
| banish_torrent | banish_torrent | Remove torrent |

## The Council — Dual-Agent Orchestrator

### Layout
- **Left Window:** Guppy (Claude or local model)
- **Right Window:** Merlin (local model, Socratic mode)
- **Isolated chats:** Independent conversation history per agent
- **Visual separation:** Different border colors and themes

### Use Cases
- **Teaching + Assistance:** Ask Merlin how something works (via questions), then ask Guppy to execute it
- **Research + Execution:** Merlin researches a topic, Guppy runs the commands
- **Dialogue:** Simulate conversations between characters

## Advanced Features

### Memory System (Persistent Sessions)
- Optional SQLite database (`guppy_memory.db`)
- Stores chat history per session (timestamped)
- Loaded at startup as "memory briefing"
- Survives app restarts

### Vision Capability (Claude Only)
- Screenshots returned as base64 image data
- Claude can analyze screen content, UI elements, text
- Enables: "What's on screen?", "Fix this error", "Read the dialog"

### Torrent Management (Merlin)
- Integration with **uTorrent WebUI** (requires configuration)
- Search YTS (movies) or 1337x (general)
- Add/remove torrents by magnet link or .torrent URL
- View active torrents with progress/speeds

### Email Integration
- **Gmail compose:** Pre-fill recipient, subject, body
- **Draft emails:** Compose in Python, open in Gmail web
- Command: `open_gmail(to="...", subject="...", body="...")`

### Report Generation
- **Call Report:** Meeting notes → PDF/docx to Documents folder
- **Order Note:** Sales data → formatted summary to Documents
- Fields: contact, date, summary, action items, outcome, follow-up

## Integrations (Framework)

### Plex Media Server (Stub)
- Configuration: `PLEX_URL`, `PLEX_TOKEN` environment variables
- Future: Query active sessions, play/queue commands

### VPN Status (Stub)
- Configuration: `VPN_CLIENT` environment variable
- Supported clients (future): NordVPN, ProtonVPN, Wireguard
- Status check and connection toggle

### Ollama Local Inference
- Models: local personas `guppy` and `merlin`
- API: `http://localhost:11434/api/chat`
- Tool use: Native support (tool_calls in response)

### Claude API (Online Mode)
- Model: `claude-sonnet-4-6` (main), `claude-haiku-4-5-20251001` (fallback)
- Vision: Screenshots passed as base64 images
- Tool use: Native support (tool_use blocks)

## Planned Features

- [ ] Global hotkey for Guppy GUI (F12 or similar)
- [ ] Voice wake-word detection ("Hey Guppy")
- [ ] Persistent UI themes (light/dark, custom colors)
- [ ] Keyboard shortcuts for common actions
- [ ] Audio notification on response ready
- [ ] Transcript logging to JSON
- [ ] Web UI for terminal-less access
- [ ] Mobile app (voice assistant on phone)
- [ ] Multi-account support (different Ryans)
- [ ] Threat detection (suspicious commands)

---

**Full Feature Set Available** ✓
