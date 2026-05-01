# Guppy: Local Tools & LLM Setup Guide

**Last updated:** 2026-04-27

This guide walks you through setting up local LLM services and integrating them with Guppy for smooth, responsive desktop control and chat.

---

## Quick Start (5 minutes)

### Prerequisites
- Python ≥ 3.12
- One of: Ollama, LMStudio, Open WebUI, or AnythingLLM
- Guppy repository cloned

### 1. Start Your LLM Service

**Option A: Ollama (Recommended)**
```powershell
# Open new PowerShell terminal
ollama serve

# In another terminal, pull a model (if needed)
ollama pull qwen2.5:7b
```

**Option B: LMStudio**
- Open LMStudio
- Load a model
- Enable "Local Server" on port 1234
- Server will listen on `http://127.0.0.1:1234`

**Option C: Open WebUI**
- Run: `docker run -p 8000:8080 ghcr.io/open-webui/open-webui:latest`
- Access: `http://localhost:8000`

**Option D: AnythingLLM**
- Run desktop app or Docker
- Configure local model source
- Listen on port 3001 by default

### 2. Verify LLM Service is Accessible

```powershell
# Check Ollama
curl http://127.0.0.1:11434/api/tags

# Check LMStudio
curl http://127.0.0.1:1234/api/models

# Check Open WebUI
curl http://127.0.0.1:8000/api/tags

# Check AnythingLLM
curl http://127.0.0.1:3001/api/health
```

### 3. Start Guppy

```powershell
# Navigate to repo
cd C:\Users\Ryan\Guppy

# Launch Web UI + API (serves on http://localhost:8081)
bin\launch_hub.bat

# OR manually:
.venv\Scripts\activate
$env:GUPPY_DEV_MODE = "1"
python -m src.guppy.cli.launch hub --dev
```

### 4. Access Web UI

Open browser to: `http://localhost:8081`

---

## Detailed Setup by Tool

### Ollama (Recommended for Local Control)

**Why Ollama:**
- ✅ Fastest setup
- ✅ True local inference (no cloud)
- ✅ GPU acceleration support (NVIDIA, AMD)
- ✅ Model caching built-in
- ✅ Guppy has direct integration

**Installation:**

1. **Download:**
   - Visit: https://ollama.ai
   - Download for Windows

2. **Install:**
   ```powershell
   # Run installer, follow prompts
   ```

3. **Start Service:**
   ```powershell
   # Open PowerShell, run:
   ollama serve

   # Output should show: "Listening on 127.0.0.1:11434"
   ```

4. **Verify Service:**
   ```powershell
   curl http://127.0.0.1:11434/api/tags
   ```

   Expected response:
   ```json
   {
     "models": [
       { "name": "qwen2.5:7b", "modified_at": "...", "size": 5000000000 },
       ...
     ]
   }
   ```

5. **Pull Models (if needed):**
   ```powershell
   # In new terminal
   ollama pull qwen2.5:7b       # Fast (5GB)
   ollama pull qwen2.5:32b      # Accurate (20GB)
   ollama pull qwen2.5-coder:14b # Code (9GB)

   # Set up aliases (for Guppy UI)
   ollama create fast -f Modelfile.fast
   ollama create code -f Modelfile.code
   ollama create main -f Modelfile.main
   ```

6. **Configure GPU (Optional but Recommended):**

   **NVIDIA (CUDA):**
   ```powershell
   # Ollama auto-detects NVIDIA GPUs
   # Verify with: nvidia-smi
   ```

   **AMD (ROCm):**
   ```powershell
   # Download ROCm: https://www.amd.com/en/technologies/rocm
   # Install, then restart computer
   # Ollama will auto-detect and use GPU
   ```

**Modelfiles (Place in repo root):**

`Modelfile.fast`:
```
FROM qwen2.5:7b
```

`Modelfile.code`:
```
FROM qwen2.5-coder:14b
```

`Modelfile.main`:
```
FROM qwen2.5:32b
```

---

### LMStudio

**Why LMStudio:**
- ✅ Beautiful GUI
- ✅ Easy model management
- ✅ Built-in local server
- ✅ Model browser with one-click download

**Setup:**

1. **Download:** https://lmstudio.ai/

2. **Install & Run**

3. **Browse & Download Models:**
   - Click "Search" in sidebar
   - Search for: `qwen2.5:7b`
   - Click download button
   - Wait for completion

4. **Start Local Server:**
   - Click "Local Server" in sidebar
   - Load a model
   - Click "Start Server"
   - Listen address: `127.0.0.1:1234`

5. **Verify:**
   ```powershell
   curl http://127.0.0.1:1234/api/models
   ```

6. **Configure Guppy:**
   - See "Guppy Configuration" section below

---

### Open WebUI

**Why Open WebUI:**
- ✅ Web-based (access from any browser)
- ✅ Supports multiple backends (Ollama, LMStudio, Hugging Face)
- ✅ Chat history & settings
- ✅ Model switching UI

**Setup:**

1. **Docker (Recommended):**
   ```powershell
   # If Docker Desktop is installed:
   docker run -d -p 8000:8080 --name open-webui ghcr.io/open-webui/open-webui:latest
   ```

2. **Or Docker Compose:**
   ```yaml
   version: '3.8'
   services:
     open-webui:
       image: ghcr.io/open-webui/open-webui:latest
       ports:
         - "8000:8080"
       environment:
         - OLLAMA_BASE_URL=http://127.0.0.1:11434
   ```

3. **Access:**
   - Open: `http://localhost:8000`
   - Create account (local)

4. **Connect LLM:**
   - Settings → Connections
   - Enter Ollama URL: `http://127.0.0.1:11434`
   - Or LMStudio: `http://127.0.0.1:1234`

---

### AnythingLLM

**Why AnythingLLM:**
- ✅ Document-aware RAG
- ✅ Workspace organization
- ✅ Multi-provider support
- ✅ Desktop + Web app

**Setup:**

1. **Download:** https://anythingllm.com/

2. **Install & Run**

3. **Configure Local Inference:**
   - Settings → Inference Provider
   - Select "Local (Ollama)" or "LMStudio"
   - Enter URL: `http://127.0.0.1:11434` (Ollama) or `:1234` (LMStudio)

4. **Create Workspace:**
   - Click "New Workspace"
   - Select model
   - Start chatting

---

## Guppy Configuration

### Default Configuration

Guppy ships with **Ollama** as the default LLM backend:

```python
# src/guppy/experience_config/runtime_config.py
DEFAULT_LLM_PROVIDER = "ollama"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
```

### Using Alternative Providers

**Option 1: Environment Variables**

```powershell
# PowerShell
$env:GUPPY_LLM_PROVIDER = "lmstudio"
$env:GUPPY_LLM_BASE_URL = "http://127.0.0.1:1234"

# Start API
python -m src.guppy.cli.launch api --dev
```

**Option 2: Edit Config File**

Edit `src/guppy/experience_config/runtime_config.py`:

```python
# For LMStudio
DEFAULT_LLM_PROVIDER = "lmstudio"
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"

# For Open WebUI (which proxies to backends)
DEFAULT_LLM_PROVIDER = "openwebui"
OPENWEBUI_BASE_URL = "http://127.0.0.1:8000"

# For AnythingLLM
DEFAULT_LLM_PROVIDER = "anythingllm"
ANYTHINGLLM_BASE_URL = "http://127.0.0.1:3001"
```

---

## Troubleshooting

### "Ollama not responding on :11434"

**Check if Ollama is running:**
```powershell
# In PowerShell, should show output:
ollama serve
# Look for: "Listening on 127.0.0.1:11434"

# If command not found, check PATH:
$env:Path -split ";"

# If Ollama installed but not in PATH, add manually:
$env:Path += ";C:\Users\Ryan\AppData\Local\Programs\Ollama"
```

**Check firewall:**
```powershell
# Allow localhost access
netsh advfirewall firewall add rule name="Ollama" dir=in action=allow program="C:\Users\Ryan\AppData\Local\Programs\Ollama\ollama.exe"
```

### "API not responding on :8081"

**Check if venv is activated:**
```powershell
# Should show (.venv) prompt
python --version

# If not, activate:
.venv\Scripts\activate
```

**Check dependencies:**
```powershell
python -m pip install -e .
python tools/dev_workflow.py test-fast
```

**Run with verbose logging:**
```powershell
$env:GUPPY_DEV_MODE = "1"
python -m src.guppy.cli.launch api --dev --verbose
```

### "Web UI shows blank chat"

1. **Check API is running:** `curl http://localhost:8081/`
2. **Check browser console:** F12 → Console tab → Look for errors
3. **Check API logs:** Should show incoming requests
4. **Verify LLM service:** `curl http://127.0.0.1:11434/api/tags`

### "Models not appearing in dropdown"

1. **Check Ollama has models:**
   ```powershell
   ollama list
   ```

2. **Pull a model if needed:**
   ```powershell
   ollama pull qwen2.5:7b
   ```

3. **Refresh Web UI:** Press Ctrl+Shift+R (hard refresh)

4. **Check API providers response:**
   ```powershell
   curl http://localhost:8081/providers
   ```

---

## Performance Tuning

### GPU Acceleration

**Check GPU is being used:**

**NVIDIA:**
```powershell
nvidia-smi

# Watch real-time:
nvidia-smi dmon
```

**AMD (ROCm):**
```powershell
# Verify ROCm is installed
rocm-smi

# Check if Ollama sees GPU
ollama run qwen2.5:7b
# In chat, monitor rocm-smi in another terminal
```

### Memory Management

**Reduce memory footprint:**

1. **Use smaller model:**
   ```powershell
   ollama pull qwen2.5:0.5b  # Tiny (240MB)
   ```

2. **Configure Ollama quantization:**
   ```powershell
   ollama pull qwen2.5:7b-q4_0  # 4-bit quantized
   ```

3. **Set keep-alive timeout:**
   - Shorter = more memory freed between requests
   - Longer = faster response (model stays in VRAM)

---

## Recommended Setup

For **smooth desktop control and chat**:

| Component | Recommended | Alternative |
|-----------|-------------|------------|
| **LLM Service** | Ollama | LMStudio |
| **Model (Fast)** | qwen2.5:7b | mistral:7b |
| **Model (Accurate)** | qwen2.5:32b | llama2:70b |
| **GPU** | NVIDIA or ROCm | CPU (slower) |
| **Guppy UI** | Web UI (localhost:8081) | Desktop Launcher |
| **Port** | 11434 (Ollama) | 1234 (LMStudio) |

---

## Next Steps

1. **Start Ollama:** `ollama serve`
2. **Pull models:** `ollama pull qwen2.5:7b`
3. **Start Guppy:** `bin\launch_hub.bat`
4. **Open Web UI:** `http://localhost:8081`
5. **Chat & test models**

---

## Support

For issues or questions:
- Check CLAUDE.md for architecture
- Review logs in `src/guppy/api/auth.py` (line 464)
- Run diagnostic: `.venv\Scripts\python.exe tools/verify_local_model_runtime.py`

