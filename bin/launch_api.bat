@echo off
REM launch_api.bat — Start the Guppy API server
REM Inference backend: Ollama (GPU-accelerated via HIP/ROCm on Windows, port 11434)
REM vLLM Docker is optional — set GUPPY_LOCAL_RUNTIME_BACKEND=vllm if running separately.
TITLE Guppy API
cd /d "%~dp0\.."

REM Guard: fail fast if the API port is already occupied (respects GUPPY_API_PORT, defaults to 8081)
if "%GUPPY_API_PORT%"=="" set GUPPY_API_PORT=8081
netstat -ano | findstr ":%GUPPY_API_PORT% " >nul 2>&1
if not errorlevel 1 (
    echo ERROR: Port %GUPPY_API_PORT% already in use. Stop the existing process first.
    echo Use:  netstat -ano ^| findstr ":%GUPPY_API_PORT%"  to find the PID.
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
