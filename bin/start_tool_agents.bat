@echo off
REM start_tool_agents.bat — Always-on workspace agent stack (dispatch + xLAM + Hermes 4)
REM
REM VRAM budget (RX 7900 XTX, 24 GB):
REM   dispatch (Qwen2.5-Omni-3B)    ~2.5 GB  — orchestrator, routes subtasks
REM   xLAM-2-8B-fc-r                ~5.0 GB  — tool-call specialist (#1 BFCL V4 ≤8B)
REM   Hermes 4 14B                   ~11.0 GB — primary workspace agent (tools + reasoning)
REM   Total                          ~18.5 GB — leaves ~5.5 GB free on 24 GB card
REM
REM Usage:
REM   Interactive:       bin\start_tool_agents.bat
REM   Task Scheduler:    Action = "Start a program", Program = full path to this bat
REM   With Guppy API:    API auto-starts all three via auto_start=True in routes_backends.py

setlocal enabledelayedexpansion
set ROOT=%~dp0..

echo.
echo  ============================================================
echo   Guppy Workspace Agent Stack
echo   dispatch (8085) + xLAM (8089) + Hermes 4 (8086)
echo   VRAM: ~18.5 GB / 24 GB
echo  ============================================================
echo.

REM ── Check if servers are already running ─────────────────────────────────────
set DISPATCH_UP=0
set XLAM_UP=0
set HERMES4_UP=0

curl -s --connect-timeout 1 http://127.0.0.1:8085/v1/models >nul 2>&1 && set DISPATCH_UP=1
curl -s --connect-timeout 1 http://127.0.0.1:8089/v1/models >nul 2>&1 && set XLAM_UP=1
curl -s --connect-timeout 1 http://127.0.0.1:8086/v1/models >nul 2>&1 && set HERMES4_UP=1

REM ── Launch missing servers ───────────────────────────────────────────────────
if %DISPATCH_UP%==0 (
    echo [agents] Starting dispatch (Qwen2.5-Omni-3B, port 8085)...
    if exist "C:\llama-cpp\launch-dispatch.bat" (
        start "Agent: dispatch" /min cmd /k "C:\llama-cpp\launch-dispatch.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-dispatch.bat not found — skipping dispatch
    )
) else (
    echo [agents] dispatch (8085) already running — skip
)

if %XLAM_UP%==0 (
    echo [agents] Starting xLAM-2-8B (port 8089)...
    if exist "C:\llama-cpp\launch-xlam.bat" (
        start "Agent: xLAM" /min cmd /k "C:\llama-cpp\launch-xlam.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-xlam.bat not found — skipping xLAM
    )
) else (
    echo [agents] xLAM (8089) already running — skip
)

if %HERMES4_UP%==0 (
    echo [agents] Starting Hermes 4 14B (port 8086)...
    if exist "C:\llama-cpp\launch-hermes-4-14b.bat" (
        start "Agent: Hermes4" /min cmd /k "C:\llama-cpp\launch-hermes-4-14b.bat"
    ) else (
        echo [agents] WARNING: C:\llama-cpp\launch-hermes-4-14b.bat not found — skipping Hermes 4
    )
) else (
    echo [agents] Hermes 4 (8086) already running — skip
)

echo.
echo [agents] Agents launching. Typical warm-up times:
echo           dispatch  ~10-20 s  (2.5 GB)
echo           xLAM      ~15-30 s  (5 GB)
echo           Hermes 4  ~30-60 s  (11 GB)
echo.
echo [agents] Verify readiness:
echo           curl http://127.0.0.1:8085/v1/models
echo           curl http://127.0.0.1:8089/v1/models
echo           curl http://127.0.0.1:8086/v1/models
echo.

REM ── Optional: wait and health-check ─────────────────────────────────────────
if "%1"=="--wait" (
    echo [agents] --wait: polling until all three agents respond (max 120 s)...
    set WAITED=0
    :WAIT_LOOP
    timeout /t 5 /nobreak >nul
    set /a WAITED+=5
    set ALL_UP=1
    curl -s --connect-timeout 1 http://127.0.0.1:8085/v1/models >nul 2>&1 || set ALL_UP=0
    curl -s --connect-timeout 1 http://127.0.0.1:8089/v1/models >nul 2>&1 || set ALL_UP=0
    curl -s --connect-timeout 1 http://127.0.0.1:8086/v1/models >nul 2>&1 || set ALL_UP=0
    if %ALL_UP%==1 (
        echo [agents] All three agents ready after %WAITED%s.
        goto DONE
    )
    if %WAITED% GEQ 120 (
        echo [agents] Timeout after 120s — check server windows for errors.
        goto DONE
    )
    goto WAIT_LOOP
)

:DONE
echo.
