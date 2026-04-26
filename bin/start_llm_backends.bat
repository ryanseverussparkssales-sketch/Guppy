@echo off
REM start_llm_backends.bat — Launch llama.cpp inference servers
REM
REM VRAM budget (RX 7900 XTX, 24 GB):
REM   Pepe 8B    ~8.5 GB  |  Gemma 4 E4B  ~8.5 GB  |  Qwen3 35B  ~19 GB
REM
REM   MODE A — Fast + Vision  (Pepe + Gemma together, ~17 GB + KV cache)
REM   MODE B — Complex/Reasoning  (Qwen3 alone, ~19 GB + KV cache)
REM   Running all three simultaneously will OOM the 24 GB card.

TITLE Guppy — Start LLM Backends

echo.
echo  RX 7900 XTX (24 GB) — choose a launch mode:
echo.
echo  [A] Fast + Vision   — Pepe 8B (8082) + Gemma 4 E4B (8080)  ~17 GB
echo  [B] Complex         — Qwen3 35B Uncensored (8083) alone     ~19 GB
echo  [Q] Quit
echo.
set /p MODE="Mode (A/B/Q): "

if /i "%MODE%"=="A" goto mode_a
if /i "%MODE%"=="B" goto mode_b
if /i "%MODE%"=="Q" goto done
echo Unknown option. Exiting.
goto done

:mode_a
echo.
echo Starting Pepe 8B (port 8082)...
start "LLM: Pepe 8B" cmd /k "C:\llama-cpp\launch-pepe.bat"
echo Starting Gemma 4 E4B (port 8080)...
start "LLM: Gemma 4 E4B" cmd /k "C:\llama-cpp\launch-gemma.bat"
echo.
echo Both backends launching. Wait for "llama server listening" in each window.
echo Verify: curl http://127.0.0.1:8082/v1/models  ^&  curl http://127.0.0.1:8080/v1/models
goto done

:mode_b
echo.
echo Starting Qwen3 35B Uncensored (port 8083)...
start "LLM: Qwen3 Uncensored" cmd /k "C:\llama-cpp\launch-qwen3.bat"
echo.
echo Backend launching. Wait for "llama server listening" (~60-90s for 35B model).
echo Verify: curl http://127.0.0.1:8083/v1/models
goto done

:done
echo.
pause
