@echo off
REM start_tool_agents.bat -- Always-on agent stack
REM
REM VRAM budget (RX 7900 XTX, 24 GB):
REM   dispatch  (Qwen2.5-3B-Instruct)  ~2 GB  -- orchestrator
REM   Hermes 3  (8B Lorablated)        ~9 GB  -- companion voice, fast tools
REM   Hermes 4  (14B)                 ~11 GB  -- workspace primary, tools + reasoning
REM   Total                           ~22 GB  -- 2 GB headroom
REM
REM xLAM (5 GB) is on-demand -- starts when tool_call tasks arrive, not at boot.
REM
REM Usage:
REM   Interactive:    bin\start_tool_agents.bat
REM   Task Scheduler: Action = "Start a program", Program = full path to this bat
REM   With Guppy API: API auto-starts all three via auto_start=True in routes_backends.py

setlocal enabledelayedexpansion
set ROOT=%~dp0..

echo.
echo  ============================================================
echo   Guppy Agent Stack
echo   dispatch (8085) + Hermes3 (8087) + Hermes4 (8086)
echo   VRAM: ~22 GB / 24 GB
echo  ============================================================
echo.

REM -- Check if servers are already running ----------------------------------------
set DISPATCH_UP=0
set HERMES3_UP=0
set HERMES4_UP=0

curl -s --connect-timeout 1 http://127.0.0.1:8085/v1/models >nul 2>&1 && set DISPATCH_UP=1
curl -s --connect-timeout 1 http://127.0.0.1:8087/v1/models >nul 2>&1 && set HERMES3_UP=1
curl -s --connect-timeout 1 http://127.0.0.1:8086/v1/models >nul 2>&1 && set HERMES4_UP=1

REM -- Launch missing servers -------------------------------------------------------
if %DISPATCH_UP%==0 (
    echo [agents] Starting dispatch (Qwen2.5-3B-Instruct, port 8085)...
    if exist "C:\llama-cpp\launch-dispatch.bat" (
        start "Agent: dispatch" /min cmd /k "C:\llama-cpp\launch-dispatch.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-dispatch.bat not found -- skipping
    )
) else (
    echo [agents] dispatch (8085) already running -- skip
)

if %HERMES3_UP%==0 (
    echo [agents] Starting Hermes 3 8B (companion voice, port 8087)...
    if exist "C:\llama-cpp\launch-hermes-3-8b.bat" (
        start "Agent: Hermes3" /min cmd /k "C:\llama-cpp\launch-hermes-3-8b.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-hermes-3-8b.bat not found -- skipping
    )
) else (
    echo [agents] Hermes 3 (8087) already running -- skip
)

if %HERMES4_UP%==0 (
    echo [agents] Starting Hermes 4 14B (workspace primary, port 8086)...
    if exist "C:\llama-cpp\launch-hermes-4-14b.bat" (
        start "Agent: Hermes4" /min cmd /k "C:\llama-cpp\launch-hermes-4-14b.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-hermes-4-14b.bat not found -- skipping
    )
) else (
    echo [agents] Hermes 4 (8086) already running -- skip
)

echo.
echo [agents] Agents launching. Typical warm-up times:
echo           dispatch  ~10-20 s  (2 GB)
echo           Hermes 3  ~20-40 s  (9 GB)
echo           Hermes 4  ~30-60 s  (11 GB)
echo.
echo [agents] Verify readiness:
echo           curl http://127.0.0.1:8085/v1/models
echo           curl http://127.0.0.1:8087/v1/models
echo           curl http://127.0.0.1:8086/v1/models
echo.

REM -- Optional: wait and health-check ---------------------------------------------
if "%1"=="--wait" (
    echo [agents] --wait: polling until all three agents respond (max 120 s)...
    set WAITED=0
    :WAIT_LOOP
    timeout /t 5 /nobreak >nul
    set /a WAITED+=5
    set ALL_UP=1
    curl -s --connect-timeout 1 http://127.0.0.1:8085/v1/models >nul 2>&1 || set ALL_UP=0
    curl -s --connect-timeout 1 http://127.0.0.1:8087/v1/models >nul 2>&1 || set ALL_UP=0
    curl -s --connect-timeout 1 http://127.0.0.1:8086/v1/models >nul 2>&1 || set ALL_UP=0
    if %ALL_UP%==1 (
        echo [agents] All three agents ready after %WAITED%s.
        goto DONE
    )
    if %WAITED% GEQ 120 (
        echo [agents] Timeout after 120s -- check server windows for errors.
        goto DONE
    )
    goto WAIT_LOOP
)

:DONE
echo.
