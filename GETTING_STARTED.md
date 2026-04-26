# Guppy: Getting Started

**Last updated:** 2026-04-22

This guide walks you through the simplest possible setup to get Guppy running with one-click desktop launchers.

---

## 📋 Prerequisites (5 min)

1. **Python 3.12+**
   ```powershell
   python --version
   ```

2. **Ollama** (or LMStudio, Open WebUI, etc.)
   - Download from: https://ollama.ai
   - Install and run: `ollama serve` (keep terminal open)

3. **This Repository**
   - Already cloned at: `C:\Users\Ryan\Guppy`

---

## 🚀 Quick Setup (3 min)

### Run One-Time Setup

Open PowerShell in the Guppy directory and run:

```powershell
cd C:\Users\Ryan\Guppy
powershell -ExecutionPolicy Bypass -File tools/setup_all.ps1
```

**What this does:**
- ✅ Checks Python installation
- ✅ Creates virtual environment (if needed)
- ✅ Installs dependencies
- ✅ Creates desktop shortcuts
- ✅ Runs diagnostics

**Output:** Three new shortcuts appear on your Desktop

---

## 💻 Using the Desktop Shortcuts

After setup, you'll have three desktop shortcuts:

### 1. **Guppy - API Server**
- Starts backend API on `http://localhost:8000`
- For: Advanced users, CLI testing, API integration
- Terminal stays open showing logs

### 2. **Guppy - Web UI** ⭐ (Recommended)
- Starts API + Web interface on `http://localhost:3000`
- For: Full chat, model selection, workspaces, settings
- Open browser to `http://localhost:3000`

### 3. **Guppy - Desktop Launcher**
- Starts native desktop application
- For: Local control without web browser
- Qt-based UI with full functionality

---

## ✅ Verify Everything Works

1. **Start Ollama** (if not already running):
   ```powershell
   ollama serve
   ```
   Leave this terminal open.

2. **Click "Guppy - Web UI"** on your Desktop
   - Terminal opens and shows startup logs
   - Wait ~3 seconds for "Listening on..."

3. **Open browser** to: `http://localhost:3000`
   - You should see the Web UI with chat interface

4. **Select a model** from dropdown and test chat:
   - Type: "Hello, who are you?"
   - Should respond using local model

---

## 🛠️ Troubleshooting

### "Ollama not responding"
- Make sure `ollama serve` is running in another terminal
- Check: `curl http://127.0.0.1:11434/api/tags`

### "Web UI shows blank"
- Wait 5 seconds for API to start
- Hard refresh browser: Ctrl+Shift+R
- Check browser console (F12) for errors

### "Models don't appear in dropdown"
- Pull a model: `ollama pull qwen2.5:7b`
- Refresh browser

### "API crashes on startup"
- Check virtual environment: `.venv\Scripts\activate`
- Check dependencies: `pip install -e .`
- Check logs in terminal window

---

## 🖥️ Web Frontend Development

If you want to work on the Web UI source (React/TypeScript), you need Node.js in addition to Python.

**Prerequisites:** Node.js 20+ and npm

```powershell
# Install web dependencies (once)
cd C:\Users\Ryan\Guppy\web
npm install

# Start the Vite dev server (hot-reload, proxies /api to port 8081)
npm run dev
# → open http://localhost:3000
```

The Vite dev server proxies `/api`, `/auth`, and `/telemetry` to the Guppy API on port 8081, so you must also have the API running (`bin\launch_api.bat` or `python -m src.guppy.cli.launch api --dev`).

**Other web commands:**

```powershell
npm run typecheck     # TypeScript type check (no emit)
npm run lint          # ESLint
npm run lint:fix      # ESLint with auto-fix
npm run format        # Prettier (writes files)
npm run format:check  # Prettier (check only, used in CI)
npm run build         # Production build → outputs to ../static/
npm run test:run      # Vitest unit tests
npm run playwright    # Playwright E2E tests (requires dev server running)
```

---

## 📚 Next Steps

- **Read TOOLS.md** for detailed setup with different LLM providers
- **Read CLAUDE.md** for architecture and development
- **Explore Web UI:** Models → Workspaces → Chat History → Settings

---

## 🎯 Commands Reference

```powershell
# Start Ollama (keep running)
ollama serve

# Pull models (optional, only if needed)
ollama pull qwen2.5:7b    # Fast (5GB)
ollama pull qwen2.5:32b   # Accurate (20GB)

# From Guppy directory:

# One-time setup
powershell -File tools/setup_all.ps1

# Run diagnostics
powershell -File tools/diagnose_and_setup.ps1

# Manual API start (after venv setup)
.venv\Scripts\activate
python -m src.guppy.cli.launch api --dev

# Manual Web UI start
.venv\Scripts\activate
python -m src.guppy.cli.launch hub --dev

# Manual Desktop Launcher start
.venv\Scripts\activate
python -m src.guppy.cli.launch launcher --dev
```

---

## 💡 Tips for Smooth Experience

1. **Keep Ollama running** in the background
   - Runs minimized: `ollama serve` in a terminal you can minimize

2. **Use Web UI for best experience**
   - Full feature set: chat history, workspaces, settings
   - No separate app needed

3. **GPU acceleration (optional but recommended)**
   - NVIDIA: Auto-detected (requires CUDA installed)
   - AMD: Install ROCm, restart computer
   - Check: `ollama run qwen2.5:7b` and monitor `nvidia-smi` or `rocm-smi`

4. **Model selection**
   - **Fast (qwen2.5:7b):** Quick responses, 5GB VRAM
   - **Accurate (qwen2.5:32b):** Better quality, 20GB VRAM
   - **Code (qwen2.5-coder:14b):** Programming tasks, 9GB VRAM

---

## 🆘 Getting Help

1. **Check diagnostics:** `powershell -File tools/diagnose_and_setup.ps1`
2. **Read detailed guide:** `TOOLS.md` (LLM setup by provider)
3. **Architecture reference:** `CLAUDE.md`
4. **Check API logs:** Look at terminal window running API

---

**All set! Click a desktop shortcut to start.** 🚀
