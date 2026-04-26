@echo off
REM open_llm_webui.bat — Open the built-in llama.cpp web UI for each backend
REM Each server must already be running (use start_llm_backends.bat first)

TITLE Guppy — Open LLM Web UIs

echo Checking which backends are up...
echo.

curl -s --max-time 1 http://127.0.0.1:8082/v1/models >nul 2>&1
if %errorlevel% equ 0 (
    echo [UP]   Pepe 8B        ^> http://127.0.0.1:8082
    start "" "http://127.0.0.1:8082"
) else (
    echo [DOWN] Pepe 8B        (port 8082 not responding)
)

curl -s --max-time 1 http://127.0.0.1:8083/v1/models >nul 2>&1
if %errorlevel% equ 0 (
    echo [UP]   Qwen3 Uncensored ^> http://127.0.0.1:8083
    start "" "http://127.0.0.1:8083"
) else (
    echo [DOWN] Qwen3 Uncensored (port 8083 not responding)
)

curl -s --max-time 1 http://127.0.0.1:8080/v1/models >nul 2>&1
if %errorlevel% equ 0 (
    echo [UP]   Gemma 4 E4B    ^> http://127.0.0.1:8080
    start "" "http://127.0.0.1:8080"
) else (
    echo [DOWN] Gemma 4 E4B    (port 8080 not responding)
)

echo.
echo Backends that are DOWN won't open. Run start_llm_backends.bat first.
echo.
pause
