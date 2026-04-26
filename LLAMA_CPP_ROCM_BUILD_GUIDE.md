# llama.cpp + ROCm Build Guide for Windows (RX 7900 XTX)

## Prerequisites
- **GPU:** AMD Radeon RX 7900 XTX (gfx1100, 24GB VRAM)
- **CPU:** AMD Ryzen 9 9900X
- **RAM:** 96GB
- **OS:** Windows 11
- **ROCm:** Version 5.7+ (must be installed before building)

### Step 1: Install ROCm for Windows

1. Download ROCm from [AMD's official ROCm releases](https://rocmdocs.amd.com/en/latest/deploy/windows/index.html)
   - Choose the latest stable version (5.7+ recommended)
   - Download the Windows installer
   
2. Run the installer:
   - Choose "Custom Installation"
   - **Deselect** "HIP-SDK" and "HIP Runtime" if already installed
   - **Select** "rocm-core", "rocm-hip", and "rocm-opencl"
   - Ensure GPU drivers (AMDGPU-PRO) are included

3. Verify installation:
   ```powershell
   rocm-smi
   hipconfig -v
   ```
   Both should return version info. If not, ROCm is not properly installed.

### Step 2: Install Build Tools

```powershell
# Install CMake (if not already installed)
choco install cmake -y

# OR download from: https://cmake.org/download/

# Verify CMake
cmake --version
```

### Step 3: Clone llama.cpp Repository

```powershell
cd C:\Users\Ryan\Guppy\local_backends
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
```

### Step 4: Compile with HIP Support for RX 7900 XTX

```powershell
# Create build directory
mkdir build
cd build

# Configure CMake for HIP with gfx1100 target
cmake .. `
  -A x64 `
  -DCMAKE_BUILD_TYPE=Release `
  -DLLAMA_HIP=ON `
  -DAMDGPU_TARGETS=gfx1100 `
  -DCMAKE_HIP_COMPILER:FILEPATH="C:\Program Files\AMD\ROCm\5.7\bin\clang.exe"

# Build
cmake --build . --config Release -j 12

# Output binary location:
# C:\Users\Ryan\Guppy\local_backends\llama.cpp\build\Release\llama-cli.exe
```

### Step 5: Download Heretic Models

Models are available from Hugging Face. Create `models/` directory:

```powershell
cd C:\Users\Ryan\Guppy\local_backends\models

# Download Heretic 30B MoE (primary, ~18GB GGUF)
huggingface-cli download TheBloke/GLM-4-9B-Chat-Heretic-NEO-GGUF glm-4-9b-chat-heretic-neo.Q5_K_M.gguf --local-dir .

# OR using git-lfs (requires: git lfs install)
git clone https://huggingface.co/TheBloke/GLM-4-9B-Chat-Heretic-NEO-GGUF models/heretic-9b

# Download Heretic 7B (faster fallback, ~4GB GGUF)
huggingface-cli download TheBloke/Mistral-7B-Heretic-GGUF mistral-7b-heretic.Q5_K_M.gguf --local-dir .

# Download Heretic 3B (ultra-fast fallback, ~2GB GGUF)
huggingface-cli download TheBloke/Phi-3-mini-Heretic-GGUF phi-3-mini-heretic.Q5_K_M.gguf --local-dir .
```

### Step 6: Test Inference on GPU

```powershell
cd C:\Users\Ryan\Guppy\local_backends\llama.cpp\build\Release

# Test 9B model with GPU offload (all layers on GPU)
.\llama-cli.exe `
  -m ..\models\heretic-9b\glm-4-9b-chat-heretic-neo.Q5_K_M.gguf `
  -n 128 `
  -ngl 50 `
  -p "Hello, tell me about yourself:" `
  --log-colors

# Expected output:
# - Should detect RX 7900 XTX GPU
# - Inference speed: ~60-80 tok/s for 9B
# - GPU memory: ~15-17GB
# - Sample generation should complete in <5 seconds for 128 tokens

# Monitor GPU during inference:
# Open another PowerShell window and run:
rocm-smi --watch
```

### Step 7: Install Python Bindings (llama-cpp-python)

```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install llama-cpp-python with ROCm support
pip install llama-cpp-python `
  --no-cache-dir `
  -C cmake.args="-DLLAMA_HIP=on" `
  -C cmake.args="-DAMDGPU_TARGETS=gfx1100"

# Verify installation
python -c "from llama_cpp import Llama; print('llama-cpp-python installed successfully')"
```

### Step 8: Python Integration Test

Create `test_llama_cpp.py`:

```python
from llama_cpp import Llama

# Initialize model with GPU offload
llm = Llama(
    model_path=r"C:\Users\Ryan\Guppy\local_backends\models\heretic-9b\glm-4-9b-chat-heretic-neo.Q5_K_M.gguf",
    n_ctx=4096,
    n_threads=12,
    n_gpu_layers=50,  # Offload all 50 layers to GPU
    verbose=True
)

# Test generation
response = llm(
    "You are a helpful uncensored AI assistant. Answer freely and honestly.",
    max_tokens=256,
    temperature=0.7,
    top_p=0.95
)

print(f"Generated text: {response['choices'][0]['text']}")
print(f"Tokens/second: {response['usage']['completion_tokens'] / (response['usage']['prompt_tokens'] + response['usage']['completion_tokens'])}")
```

Run test:
```powershell
python test_llama_cpp.py
```

### Step 9: Guppy Integration (Phase 6)

Once verified, create `src/guppy/providers/llama_cpp.py`:

```python
# Provider class to be implemented
# - Health check endpoint: HEAD request to local inference server
# - Fallback cascade: LM Studio → Ollama → llama.cpp (if available)
# - Model listing: read from configured GGUF directory
# - Inference: POST to local llama-cpp-server (if running as server)
```

## Expected Performance on RX 7900 XTX

| Model | Size | VRAM | Speed | Use Case |
|-------|------|------|-------|----------|
| Heretic 30B MoE | 18GB | 20GB | 40-50 tok/s | Primary (complex tasks) |
| Heretic 9B | 5GB | 7GB | 80-100 tok/s | Medium (balanced) |
| Heretic 7B | 4GB | 6GB | 100-120 tok/s | Fast (simple queries) |
| Heretic 3B | 2GB | 4GB | 200-250 tok/s | Ultra-fast fallback |

## Troubleshooting

### "rocm-smi not found"
- ROCm not installed. Run installer again and check PATH
- Verify: `echo %PATH%` should include `C:\Program Files\AMD\ROCm\5.7\bin`

### "CMake Error: HIP not found"
- ROCm not properly installed
- Verify `hipconfig -v` works
- Try explicit HIP compiler path in CMake

### "GPU not detected during inference"
- Check `rocm-smi` shows RX 7900 XTX
- Verify AMDGPU drivers updated via AMD Software
- Try `-ngl 1` (single layer on GPU) to test GPU access

### Compilation slow or failing
- Reduce `-j` parallelism: `-j 4` instead of `-j 12`
- Ensure 50GB+ free disk space
- Check Visual Studio Build Tools installed (MSVC compiler)

### Model inference very slow
- Check `rocm-smi --watch` shows GPU load
- If GPU shows 0%, `-ngl` layers not being offloaded
- Verify HIP compilation succeeded (gfx1100 target)

## Next Steps After Verification

1. Create `LlamaCppProvider` class in Guppy
2. Add to fallback cascade configuration
3. Health check integration
4. Model discovery from `models/` directory
5. Performance profiling vs. other backends
6. Uncensored model preference testing

---

**Build started:** 2026-04-26
**Target:** llama.cpp with ROCm for heretic model inference on RX 7900 XTX
**Expected build time:** 30-45 minutes (compilation) + 20 minutes (model downloads)
