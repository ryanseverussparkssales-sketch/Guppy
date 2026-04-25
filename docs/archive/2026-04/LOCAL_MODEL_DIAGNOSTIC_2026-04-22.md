# Local Model Stability & Hardware Utilization Diagnostic

**Date:** 2026-04-22  
**System:** Windows PC with AMD GPU  
**Goal:** Diagnose why models aren't using full hardware potential

---

## Phase 1: System Diagnostics

Run these commands to understand your current setup.

### 1.1 Check AMD GPU Availability

```powershell
# Check installed AMD drivers
dxdiag
# Look for: AMD Radeon GPU listed

# Or check via PowerShell
Get-CimInstance CIM_VideoController
```

**Expected output:** Should show AMD GPU name and VRAM

**If no GPU shows:**
- AMD drivers not installed
- GPU not detected by Windows
- Need to install/update AMD drivers

### 1.2 Check Ollama Configuration

```powershell
# Start Ollama (if not running)
ollama serve

# In another terminal, check Ollama status
ollama list
```

**Expected output:**
```
NAME                    ID              SIZE    MODIFIED
guppy:latest           abc123...       20GB    2 hours ago
guppy-fast:latest      def456...       5GB     1 week ago
guppy-code:latest      ghi789...       9GB     3 days ago
```

**If empty:**
- No models installed
- Need to pull models first

### 1.3 Check If GPU Acceleration is Active

```powershell
# Check Ollama logs for GPU usage
# Logs are at: %USERPROFILE%\AppData\Local\Ollama\logs\

# Or run a test query and watch the output
ollama run guppy "Hello, are you using GPU acceleration?"
# Look at the response time - if <1 second, likely using GPU
```

**Indicators of GPU usage:**
- Responses in <2 seconds for simple queries
- GPU Task Manager shows activity
- Ollama logs mention "GPU" or "CUDA" or "ROCm"

**Indicators of CPU-only:**
- Responses take 10+ seconds
- GPU Task Manager shows 0% utilization
- Logs don't mention GPU

---

## Phase 2: Detailed Hardware Check

### 2.1 AMD ROCm Support

AMD GPU acceleration in Ollama requires ROCm (ROCm Compute Platform).

```powershell
# Check if ROCm is installed
# ROCm for AMD GPUs: https://rocmdocs.amd.com/

# If installed, check version
rocm-smi

# Expected: GPU device number, used/available memory, etc.
```

**AMD GPU Compatibility:**
- RDNA2 and newer (RX 6700+): Full ROCm support
- RDNA1 (RX 5700+): Supported but less tested
- Older Polaris: Limited/experimental support

**If ROCm not installed:**
- Download from: https://rocmdocs.amd.com/en/latest/deploy/windows/quick_start.html
- Install with GPU support
- Restart Ollama

### 2.2 Check Ollama AMD GPU Configuration

Ollama should auto-detect AMD ROCm if available.

```powershell
# Check Ollama's GPU detection
# Logs at: $env:LOCALAPPDATA\Ollama\logs\

# Or set environment variable to enable debug logging
$env:OLLAMA_DEBUG = "1"
ollama serve
# Look for GPU detection messages
```

**Good signs in logs:**
```
Detecting AMDGPU devices
Found AMD device: /dev/dri/renderD128
Allocating 8GB VRAM to model
```

**Bad signs:**
```
No AMD devices detected
GPU acceleration disabled - using CPU only
```

---

## Phase 3: Performance Baseline

### 3.1 Benchmark Current Setup

```powershell
# Start fresh Ollama with no other tasks
# Test inference speed for different models

# Test 1: Simple query (Fast model)
$start = Get-Date
ollama run guppy-fast "What is 2+2?"
$elapsed = (Get-Date) - $start
Write-Host "Response time: $($elapsed.TotalSeconds) seconds"

# Test 2: Longer query (32B model)
$start = Get-Date
ollama run guppy "Write a 3-sentence poem about the moon."
$elapsed = (Get-Date) - $start
Write-Host "Response time: $($elapsed.TotalSeconds) seconds"
```

**Expected performance:**
```
Benchmark Results (for reference):
- GPU (AMD RDNA2, 8GB vRAM):
  * guppy-fast (7B): 0.5-1.0 sec
  * guppy (32B): 3-5 sec

- CPU (Intel i7, 12 cores):
  * guppy-fast (7B): 3-5 sec
  * guppy (32B): 30+ sec

- CPU (AMD Ryzen 5, 6 cores):
  * guppy-fast (7B): 5-8 sec
  * guppy (32B): 60+ sec
```

**If your times are much slower:**
- Models likely running on CPU only
- GPU not being utilized
- Need to check ROCm setup

### 3.2 Monitor Hardware Usage During Inference

**Windows Task Manager:**
1. Open Task Manager (Ctrl+Shift+Esc)
2. Go to "Performance" tab
3. Watch GPU utilization while running `ollama run guppy "test"`
4. Should see GPU usage spike to 50-100%

**AMD GPU Monitor (if available):**
- Look for Radeon Software/AMD driver tools
- Check GPU load, memory used, temperature

**If GPU shows 0% usage:**
- GPU acceleration not working
- Ollama using CPU fallback
- Likely ROCm not properly installed

---

## Phase 4: Diagnosis Decision Tree

### Decision 1: Is Ollama using GPU?

**Test:**
```powershell
ollama run guppy-fast "test" # Should take <1 sec if GPU
```

**If <1 second → GPU working, skip to optimization**

**If 5+ seconds → Likely CPU only, continue below**

### Decision 2: Is AMD GPU available to Windows?

**Test:**
```powershell
Get-CimInstance CIM_VideoController | Select-Object Name, AdapterMemory
```

**If shows AMD GPU → GPU available, check ROCm**

**If no AMD GPU → GPU not detected by Windows, drivers needed**

### Decision 3: Is ROCm installed?

**Test:**
```powershell
rocm-smi --showid
```

**If command works → ROCm installed, check Ollama logs for errors**

**If "rocm-smi not found" → ROCm not installed, install from AMD**

### Decision 4: Ollama Configuration

**Check logs:**
```powershell
Get-Content $env:LOCALAPPDATA\Ollama\logs\* -Tail 100
```

**Look for:**
- "GPU acceleration enabled" → Working ✅
- "No compatible GPU found" → Need to troubleshoot ROCm
- "Using CPU" → Fallback mode, not using GPU

---

## Common Issues & Fixes

### Issue 1: "No AMD Devices Detected"

**Cause:** ROCm not installed or not found by Ollama

**Fix:**
1. Install ROCm from: https://rocmdocs.amd.com/en/latest/deploy/windows/quick_start.html
2. Restart computer (ROCm needs reboot)
3. Restart Ollama
4. Check logs again

### Issue 2: "Out of GPU Memory"

**Cause:** Model too large for available VRAM

**Fix:**
- Run smaller model: `ollama run guppy-fast` (5GB) instead of guppy (20GB)
- Or reduce batch size in Ollama config
- Or increase GPU memory allocation if available

**Ollama config** at `$env:LOCALAPPDATA\Ollama\ollama\Modelfile`:
```
FROM guppy:latest
PARAMETER num_gpu 35  # Adjust based on available memory
```

### Issue 3: Slow Responses on GPU

**Cause:** 
- GPU overloaded (multiple models running)
- Not enough VRAM (model being partially swapped to RAM)
- Other applications using GPU

**Fix:**
- Close other GPU-intensive apps
- Restart Ollama to free memory
- Use smaller model (guppy-fast instead of guppy)
- Check GPU temperature: `rocm-smi --showtemp`

### Issue 4: Driver Conflicts

**Cause:** Outdated or conflicting AMD drivers

**Fix:**
```powershell
# Update AMD drivers
# Go to: https://www.amd.com/en/support
# Search for your GPU model
# Download latest driver
# Uninstall old, install new
# Restart
```

---

## What You Need to Do NOW

**Run this sequence:**

```powershell
# 1. Check what models are installed
ollama list

# 2. Check GPU availability
Get-CimInstance CIM_VideoController | Select-Object Name

# 3. Check if ROCm is installed
rocm-smi --showid

# 4. Run a performance test
$start = Get-Date
ollama run guppy-fast "What is the capital of France?"
$elapsed = (Get-Date) - $start
"Time: $($elapsed.TotalSeconds) seconds"

# 5. Check Task Manager GPU usage while above runs
# Open Task Manager → Performance → GPU

# 6. Check Ollama logs
Get-Content $env:LOCALAPPDATA\Ollama\logs\* -Tail 50
```

**Send me the output of:**
- Step 1: Which models are installed
- Step 4: How long guppy-fast took
- Step 6: Any GPU-related messages in logs

---

## Next Steps Based on Findings

**If GPU is working (guppy-fast <1 sec):**
- Skip to Phase 5: Optimization
- Focus on Ollama tuning for maximum performance

**If GPU is not working (guppy-fast 5+ sec):**
- Install/update ROCm
- Verify AMD drivers
- Re-test

**If uncertain:**
- Share the diagnostic output above
- We'll pinpoint the exact issue
- Implement targeted fix

---

## Phase 5: Optimization (if GPU is working)

Once GPU acceleration is confirmed working:

1. **Configure optimal memory allocation**
   - Set `num_gpu` parameter based on your VRAM
   - Default: 35 layers (good for 8GB+)
   - Reduce to 25 for 6GB, 15 for 4GB

2. **Model selection**
   - `guppy-fast` (5GB) for quick responses
   - `guppy-code` (9GB) for coding tasks
   - `guppy` (20GB) only if you have plenty of VRAM

3. **Parallel inference**
   - Only run one model at a time
   - Switch models = full unload + reload
   - Can run in parallel if total VRAM allows

4. **Temperature monitoring**
   - AMD GPUs: safe up to 80-90°C
   - Above 90°C: throttling occurs (slower)
   - Consider adding cooling if running hot

---

## Web UI Integration

Once local models are stable:

1. **Web UI needs to know available models**
   - Currently hardcoded in `api/routes/chat.py`
   - Need dynamic model discovery from Ollama

2. **Model switching needs to work**
   - Web UI lets user select model
   - API loads selected model from Ollama
   - Switch time: typically 5-10 seconds

3. **Performance visibility**
   - Show which model is active
   - Show response time
   - Show GPU/CPU usage (if available)

---

## Files to Share for Diagnosis

After running the diagnostics above, please provide:
1. Output of `ollama list`
2. Output of `Get-CimInstance CIM_VideoController`
3. Response time for `guppy-fast "test"` test
4. Screenshot of Task Manager GPU usage while running inference
5. Last 50 lines of Ollama logs

This will help pinpoint exactly what's wrong and how to fix it.
