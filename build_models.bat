@echo off
REM build_models.bat — Rebuild Guppy and Merlin Ollama models on qwen2.5:32b
REM =========================================================================
REM Run this once after qwen2.5:32b finishes downloading.
REM Re-run any time you want to update a persona or swap the base model.

echo ============================================
echo Guppy Model Builder
echo ============================================
echo.

REM Check qwen2.5:32b is available
ollama list | findstr "qwen2.5:32b" >nul 2>&1
if errorlevel 1 (
    echo ERROR: qwen2.5:32b not found in Ollama.
    echo Pull it first with:  ollama pull qwen2.5:32b
    pause
    exit /b 1
)

echo [1/2] Building guppy model...
ollama create guppy -f Modelfile.guppy
if errorlevel 1 (
    echo ERROR: Failed to build guppy model.
    pause
    exit /b 1
)
echo       Done.
echo.

echo [2/2] Building merlin model...
ollama create merlin -f Modelfile.merlin
if errorlevel 1 (
    echo ERROR: Failed to build merlin model.
    pause
    exit /b 1
)
echo       Done.
echo.

echo ============================================
echo Both models rebuilt on qwen2.5:32b.
echo ============================================
echo.
ollama list
echo.
pause
