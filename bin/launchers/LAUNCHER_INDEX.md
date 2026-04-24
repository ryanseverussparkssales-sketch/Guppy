# Guppy Launcher Index

**Location:** `bin/launchers/`  
**Purpose:** One-click launchers for different scenarios

---

## Quick Start (Pick One)

### 🚀 Normal Operation (90% of cases)
```batch
run_full_stack.bat
```
**What:** Starts Ollama + API + Web UI  
**When:** You want everything working  
**Time:** ~30 seconds  
**Ports:** Ollama:11434, API:8000, Web UI:3000  

---

### ⚡ Fast Mode (Out of Compute)
```batch
run_with_small_model.bat
```
**What:** Uses smaller model for faster responses  
**When:** Your GPU is out of memory or system is slow  
**Time:** ~0.5-2 seconds per response  
**Model:** qwen2.5:7b (5GB)  

---

### 🌐 Cloud Provider (No Local Compute)
```batch
run_with_claude.bat
```
**What:** Uses Claude API instead of local Ollama  
**When:** You're out of GPU/compute or want highest quality  
**Time:** 2-5 seconds per response  
**Cost:** ~$0.003-0.015 per message  
**Requirement:** Valid `sk-ant-*` API key in Settings  

---

### 🖥️ API Only (Development)
```batch
run_api_only.bat
```
**What:** Just the API server, no Web UI  
**When:** Testing API endpoints or developing frontend  
**Port:** 8000  
**Test:** `curl http://localhost:8000/api/health`  

---

### 📱 Web UI Only (API Already Running)
```batch
run_web_ui_only.bat
```
**What:** Just the Web UI, assumes API is running  
**When:** API is already in another terminal  
**Port:** 3000  
**Requires:** API already running at http://localhost:8000  

---

### 🐛 Debug Mode (UI Testing)
```batch
run_web_ui_debug_mode.bat
```
**What:** Web UI with mock responses if API unavailable  
**When:** Testing UI without API backend  
**Port:** 3000  
**Feature:** Shows mock chat responses  

---

## Utility Scripts

### 🏥 Health Check
```batch
test_setup.bat
```
**What:** Tests all dependencies and system setup  
**Results:**
- ✓ All required software installed
- ✓ All ports available
- ✓ Database and config files ready
- ⚠️ Warnings for missing components

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+C | Stop current service (in terminal) |
| Ctrl+Shift+Esc | Open Task Manager (force-kill if needed) |
| F5 | Refresh browser |
| Ctrl+Shift+R | Hard refresh (clear cache) |

---

## Common Issues & Solutions

### "Ollama not found"
```batch
REM Install Ollama from https://ollama.ai
REM Then restart this launcher
```

### "Port already in use"
**If port 8000 in use:**
```batch
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**If port 3000 in use:**
```batch
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

### "Out of GPU memory"
```batch
REM Use small model launcher instead
run_with_small_model.bat
REM Or use cloud provider
run_with_claude.bat
```

### "API not responding"
```batch
REM Check Ollama is running
tasklist | findstr ollama

REM If not, restart it
taskkill /IM ollama.exe /F
ollama serve
```

---

## Terminal Commands (Manual Launch)

### If you prefer terminal control:

**Terminal 1 - Start Ollama:**
```powershell
ollama serve
```

**Terminal 2 - Start API:**
```powershell
.venv\Scripts\activate
$env:GUPPY_DEV_MODE = 1
python -m src.guppy.cli.launch api --dev
```

**Terminal 3 - Start Web UI:**
```powershell
cd web
npm run dev
```

Then open browser to: **http://localhost:3000**

---

## Full Documentation

For detailed troubleshooting and setup guide, see:
**[README.md](README.md)** - Complete guide with troubleshooting and manual commands

---

## Launcher Cheat Sheet

```
NORMAL            →  run_full_stack.bat
SLOW COMPUTER     →  run_with_small_model.bat
NO COMPUTE        →  run_with_claude.bat
API ONLY          →  run_api_only.bat
WEB UI ONLY       →  run_web_ui_only.bat
DEBUG MODE        →  run_web_ui_debug_mode.bat
CHECK SETUP       →  test_setup.bat
```

---

## What Each Port Does

| Port | Service | URL |
|------|---------|-----|
| 11434 | Ollama | http://localhost:11434/api/tags |
| 8000 | API | http://localhost:8000/api/health |
| 3000 | Web UI | http://localhost:3000 |

---

## Environment Variables (Advanced)

**For manual control, set these before starting:**

```powershell
# Use specific model
$env:GUPPY_DEFAULT_MODEL = "qwen2.5:7b"

# Use different provider
$env:GUPPY_LLM_PROVIDER = "anthropic"  # or "openai", "google"

# Change API port
$env:PORT = 8001

# Enable debug logging
$env:GUPPY_DEV_MODE = 1

# Set Ollama base URL
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
```

---

## Next Steps

1. **Run health check:**
   ```batch
   test_setup.bat
   ```

2. **Pick appropriate launcher** (see cheat sheet above)

3. **Double-click the .bat file**

4. **Browser opens automatically** to http://localhost:3000

5. **Type a message and chat!**

---

## Support

If something doesn't work:
1. Check [README.md](README.md) for troubleshooting
2. Run `test_setup.bat` to diagnose issues
3. Check terminal windows for error messages
4. Review common issues above

All launchers are designed to handle common failures gracefully!
