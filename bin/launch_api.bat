@echo off
REM launch_api.bat — Start the Guppy API server
REM Inference backend: Ollama (GPU-accelerated via HIP/ROCm on Windows, port 11434)
REM vLLM Docker is optional — set GUPPY_LOCAL_RUNTIME_BACKEND=vllm if running separately.
TITLE Guppy API
cd /d "%~dp0\.."

REM Guard: fail fast if port 8081 is already occupied
netstat -ano | findstr ":8081 " >nul 2>&1
if not errorlevel 1 (
    echo ERROR: Port 8081 already in use. Stop the existing process first.
    echo Use:  netstat -ano ^| findstr ":8081"  to find the PID.
    pause
    exit /b 1
)

REM Check Ollama is reachable
curl -s http://localhost:11434/ >nul 2>&1
if errorlevel 1 (
    echo WARNING: Ollama not responding on port 11434. Start Ollama before using chat.
)

.venv\Scripts\python.exe src\guppy\cli\launch.py api
pause
