# Guppy: Getting Started

**Last updated:** 2026-04-27

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

### Run One-Time Bootstrap

Open PowerShell in the Guppy directory and run:

```powershell
cd C:\Users\Ryan\Guppy
powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
```

**What this does:**
- ✅ Checks Python installation
- ✅ Creates virtual environment
- ✅ Installs all dependencies (dev extras included)

**Then update the desktop shortcut:**
```powershell
powershell -ExecutionPolicy Bypass -File tools/ensure_desktop_launcher.ps1
```

---

## 💻 Using the Desktop Shortcuts

After setup, you'll have three desktop shortcuts:

### 1. **Guppy - API Server**
- Starts backend API on `http://localhost:8081`
- For: Advanced users, CLI testing, API integration
- Terminal stays open showing logs

### 2. **Guppy - Web UI** ⭐ (Recommended)
- Starts API + serves the built Web UI on `http://localhost:8081`
- For: Full chat, model selection, workspaces, settings
- Open browser to `http://localhost:8081`

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

2. **Click "Guppy - Web UI"** on your Desktop (or run `bin\launch_hub.bat`)
   - Terminal opens and shows startup logs
   - Wait ~3 seconds for "Listening on..."

3. **Open browser** to: `http://localhost:8081`
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
- Reinstall deps: `python -m pip install -e .[dev]`
- Check logs in terminal window

---

## 📚 Next Steps

- **Read TOOLS.md** for detailed setup with different LLM providers
- **Read CLAUDE.md** for architecture and development
- **Explore Web UI:** Chat → Launch Control → Personas → Instructions → Tools → Settings

---

## 🎯 Commands Reference

```powershell
# Start Ollama (keep running)
ollama serve

# Pull models (optional, only if needed)
ollama pull qwen2.5:7b    # Fast (5GB)
ollama pull qwen2.5:32b   # Accurate (20GB)

# From Guppy directory:

# One-time bootstrap (creates .venv and installs deps)
powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev

# Run diagnostics
.venv\Scripts\python.exe tools/verify_local_model_runtime.py
.venv\Scripts\python.exe tools/dev_workflow.py dev-check

# Manual Web UI + API start (serves on http://localhost:8081)
.venv\Scripts\activate
python -m src.guppy.cli.launch hub --dev

# OR use the launcher batch file
bin\launch_hub.bat

# Manual API-only start
.venv\Scripts\activate
python -m src.guppy.cli.launch api --dev

# Dev Web UI with hot-reload (serves on http://localhost:5173, proxies to :8081)
cd web && npm run dev
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

1. **Run diagnostics:** `.venv\Scripts\python.exe tools/verify_local_model_runtime.py`
2. **Read detailed guide:** `TOOLS.md` (LLM setup by provider)
3. **Architecture reference:** `CLAUDE.md`
4. **Check API logs:** Look at terminal window running API

---

**All set! Click a desktop shortcut to start.** 🚀
