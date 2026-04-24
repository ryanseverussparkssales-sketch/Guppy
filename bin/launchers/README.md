# Guppy Launchers - Quick Start & Troubleshooting

**Location:** `bin/launchers/`  
**Purpose:** One-click launcher scripts with fallback options for out-of-compute scenarios

---

## Quick Start (90% of cases)

### Option 1: Full Stack (Recommended)
```batch
run_full_stack.bat
```
Starts:
- ✅ Ollama (if not running)
- ✅ API server on :8000
- ✅ Web UI on :3000
- ✅ Browser opens automatically

### Option 2: Web UI Only (API already running)
```batch
run_web_ui_only.bat
```
For when API is already running in another terminal.

### Option 3: API Only (Testing/Development)
```batch
run_api_only.bat
```
For testing API endpoints without Web UI.

---

## When Out of Compute Resources ⚠️

### Problem: "Ollama not responding" or very slow
**Root Cause:** Model is too large for your GPU/RAM, or Ollama crashed

#### Solution 1: Use Smaller Model (FASTEST)
```batch
run_with_small_model.bat
```
This will:
- Switch to `qwen2.5:7b` (smaller, faster)
- Or fall back to `guppy-fast` alias if available
- Restart API with smaller model

**Expected speed:** 0.5-2 seconds per response

#### Solution 2: Switch to Cloud Provider
```batch
run_with_claude.bat
```
This will:
- Use Claude API instead of local Ollama
- Requires valid `sk-ant-*` key in Guppy Settings
- Much faster responses, but costs money

**Expected speed:** 2-5 seconds per response

#### Solution 3: Pure Web UI Mode (No AI)
```batch
run_web_ui_debug_mode.bat
```
This will:
- Start Web UI only
- Allow browsing chat history
- Mock responses if Ollama unavailable
- Good for testing UI without compute

---

## Manual Terminal Commands

If you prefer terminal control, use these commands directly:

### Start Ollama Service
```powershell
# Open new PowerShell terminal and run:
ollama serve

# You should see:
# "Listening on 127.0.0.1:11434"

# To verify it's working:
curl http://127.0.0.1:11434/api/tags
```

### Start API Server
```powershell
# Activate venv first
.venv\Scripts\activate

# Set dev mode
$env:GUPPY_DEV_MODE = 1

# Start API on port 8000
python -m src.guppy.cli.launch api --dev

# You should see:
# "Uvicorn running on http://127.0.0.1:8000"
```

### Start Web UI (requires Node.js)
```powershell
# In web directory
cd web

# Install dependencies (first time only)
npm install

# Start dev server on port 3000
npm run dev

# You should see:
# "Local: http://localhost:3000"

# To build for production:
npm run build
```

### Run Everything in One Terminal (Quick & Dirty)
```powershell
# Terminal 1 - Ollama
ollama serve

# Terminal 2 - API
.venv\Scripts\activate
$env:GUPPY_DEV_MODE = 1
python -m src.guppy.cli.launch api --dev

# Terminal 3 - Web UI
cd web
npm run dev
```

---

## Troubleshooting Guide

### Problem 1: "Ollama not found" or "command not found"
**Cause:** Ollama not installed or not in PATH

**Solution:**
```powershell
# Check if Ollama is installed
ollama --version

# If not found, install from https://ollama.ai
# Then add to PATH:
$env:Path += ";C:\Users\Ryan\AppData\Local\Programs\Ollama"

# Verify
ollama --version
```

### Problem 2: Ollama running but "no response" or hanging
**Cause:** Model is too large, out of VRAM

**Quick Fix:**
```powershell
# Kill Ollama and restart with smaller model
taskkill /IM ollama.exe /F

# Wait 5 seconds
Start-Sleep -Seconds 5

# Pull smaller model
ollama pull qwen2.5:7b

# Or use alias if available
ollama pull guppy-fast

# Start Ollama again
ollama serve
```

### Problem 3: API server won't start
**Cause:** Port 8000 already in use or missing dependencies

**Solution:**
```powershell
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F

# Or use different port
$env:PORT = 8001
python -m src.guppy.cli.launch api --dev

# If missing dependencies:
pip install -e .
python tools/dev_workflow.py test-fast
```

### Problem 4: Web UI blank or shows "Cannot reach API"
**Cause:** API not running or port mismatch

**Solution:**
```powershell
# Check API is running
curl http://localhost:8000/api/health
# Should return: {"status": "ok"}

# Check Web UI config points to correct API
# File: web/.env or web/src/api/client.ts
# Should have: API_URL=http://localhost:8000

# If using different port, update config and rebuild
npm run build
```

### Problem 5: Chat says "Failed to send message"
**Cause:** Either Ollama is down or cloud API key is invalid

**Solution:**
```powershell
# Test Ollama is working
ollama list
# Should show: qwen2.5:7b, etc.

# If no models, pull one
ollama pull qwen2.5:7b

# Test API can call Ollama
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test", "mode": "auto"}'
# Should return: {"response": "...", "session_id": "test"}

# If using cloud provider, verify key
# Settings → Providers → Check key is valid
```

### Problem 6: "Port 3000 in use" for Web UI
**Cause:** Another app using port 3000

**Solution:**
```powershell
# Find what's using port 3000
netstat -ano | findstr :3000

# Kill the process
taskkill /PID <PID> /F

# Or use different port
cd web
$env:VITE_PORT = 3001
npm run dev
# Then open http://localhost:3001
```

### Problem 7: Models loading very slowly (not hanging, just slow)
**Cause:** GPU not being used or RAM is swapped to disk

**Check GPU usage:**
```powershell
# For NVIDIA
nvidia-smi
# Watch real-time:
nvidia-smi dmon

# For AMD ROCm
rocm-smi
# Watch real-time:
rocm-smi --watch
```

**If GPU not being used:**
- Make sure you installed GPU drivers (NVIDIA/AMD)
- ROCm requires system restart after installation
- Ollama auto-detects on restart

**If GPU is full:**
```powershell
# Use smaller model
ollama pull qwen2.5:7b  # 5GB instead of 20GB

# Or configure Ollama to use less VRAM
# Set OLM_KEEP_ALIVE to lower value
```

---

## Performance Tips

### Fast Responses (< 1 second)
- Use `qwen2.5:7b` (5GB, ~0.5s response)
- Use `guppy-fast` alias (pre-optimized)
- Use GPU acceleration (NVIDIA or ROCm)

### Better Responses (3-5 seconds)
- Use `qwen2.5:32b` (20GB, more accurate)
- Or use Claude API (cloud provider)

### Out of Compute?
- Switch to cloud provider (Claude, OpenAI, Google)
- Use smaller model with lower quality
- Use cached responses (if same question asked before)

---

## Testing Your Setup

### Quick Health Check
```powershell
# Run this to test everything
./test_setup.bat

# Or manually:
echo "Testing Ollama..."
curl http://127.0.0.1:11434/api/tags

echo "Testing API..."
curl http://localhost:8000/api/health

echo "Testing Web UI..."
start http://localhost:3000
```

---

## What Each Launcher Does

### `run_full_stack.bat`
1. Checks if Ollama is running
2. If not, starts Ollama service
3. Waits for Ollama to be ready (up to 30 seconds)
4. Activates venv
5. Starts API server (port 8000)
6. Starts Web UI (port 3000)
7. Opens browser to http://localhost:3000

### `run_web_ui_only.bat`
1. Assumes API is already running
2. Activates venv (just for npm)
3. Starts Web UI (port 3000)
4. Opens browser

### `run_api_only.bat`
1. Checks if Ollama is running
2. If not, starts Ollama
3. Activates venv
4. Starts API (port 8000)
5. Shows API is ready message

### `run_with_small_model.bat`
1. Kills any running Ollama
2. Pulls `qwen2.5:7b` (if not already pulled)
3. Sets `GUPPY_DEFAULT_MODEL=qwen2.5:7b`
4. Starts API with smaller model
5. Starts Web UI

### `run_with_claude.bat`
1. Sets `GUPPY_LLM_PROVIDER=anthropic`
2. Assumes Claude API key is in Guppy Settings
3. Starts API (no Ollama needed)
4. Starts Web UI
5. **Note:** Requires valid `sk-ant-*` key

### `run_web_ui_debug_mode.bat`
1. Disables API requirement
2. Starts Web UI only
3. Shows mock responses if API unavailable
4. Good for UI testing/debugging

---

## Emergency Recovery

### If everything is broken:
```powershell
# Kill all Guppy processes
taskkill /IM ollama.exe /F
taskkill /IM python.exe /F  # Be careful with this!
taskkill /IM node.exe /F

# Wait 10 seconds
Start-Sleep -Seconds 10

# Start fresh
./run_full_stack.bat
```

### If database is corrupted:
```powershell
# Backup current database
Copy-Item "data\guppy.db" "data\guppy.db.backup"

# Delete corrupted database
Remove-Item "data\guppy.db"

# Restart - new database will be created
./run_full_stack.bat
```

### If npm/venv is broken:
```powershell
# Reinstall dependencies
pip install -e .
cd web
npm install
npm run build
cd ..

# Try again
./run_full_stack.bat
```

---

## FAQ

**Q: Why is the first response slow?**
A: Model is loading into VRAM. Subsequent responses are faster. First response typically takes 3-10 seconds depending on model size.

**Q: Can I run multiple instances of Guppy?**
A: No, Ollama/API/Web UI only run on single ports. You'd need to change ports in config and restart.

**Q: What if I don't have a GPU?**
A: CPU inference will be slower (10-30 seconds per response). Consider using smaller model or cloud provider.

**Q: Can I use Guppy on my phone?**
A: Yes! Just access `http://<computer-ip>:3000` from your phone (must be same network). API needs to be configured to allow external connections.

**Q: How much disk space does Guppy use?**
A: Ollama models: 5-20GB depending on model size. Guppy database: 1-10MB. Total: Usually under 30GB.

---

## Next Steps

1. **Pick a launcher based on your scenario:**
   - Full stack → `run_full_stack.bat`
   - Out of compute → `run_with_small_model.bat`
   - Want to use Claude → `run_with_claude.bat`

2. **Test it works:**
   - Type a message in Web UI
   - Should see response within 10 seconds

3. **If it doesn't work:**
   - Open a PowerShell terminal
   - Run the manual commands from "Manual Terminal Commands" section
   - Check which step fails and see troubleshooting

4. **Bookmark this README:**
   - It has the commands you'll need when things break
   - Everything is recoverable with the commands here
