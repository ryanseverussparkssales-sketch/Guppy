@echo off
REM build_models.bat — Rebuild all Guppy Ollama persona models
REM =========================================================================
REM Run once after pulling base models, or any time you update a Modelfile.
REM
REM Model roster:
REM   guppy-fast    — qwen2.5:7b           (simple/fast butler, ~5 GB, full VRAM)
REM   vault-scraper — qwen2.5:7b           (seed vault extraction, shared 7b blob)
REM   merlin-code   — qwen2.5-coder:14b    (code review/debug, ~9 GB)
REM   guppy         — qwen2.5:32b          (complex butler tasks, ~20 GB)
REM   merlin        — qwen2.5:32b          (Socratic teaching, shared 32b blob)
REM
REM VRAM notes (RX 7900 XTX, 24 GB):
REM   7B + 14B can be warm simultaneously (~14 GB)
REM   32B needs exclusive VRAM (~20 GB) — evicts others when loaded
REM   Two 7B models share one blob — zero extra VRAM cost

echo ============================================
echo Guppy Model Builder
echo ============================================
echo.

REM ── Check / pull base models ─────────────────────────────────────────────────
ollama list | findstr "qwen2.5:7b" >nul 2>&1
if errorlevel 1 (
    echo [PULL] qwen2.5:7b not found. Pulling now ^(~5 GB^)...
    ollama pull qwen2.5:7b
    if errorlevel 1 ( echo ERROR: qwen2.5:7b pull failed. & pause & exit /b 1 )
)

ollama list | findstr "qwen2.5-coder:14b" >nul 2>&1
if errorlevel 1 (
    echo [PULL] qwen2.5-coder:14b not found. Pulling now ^(~9 GB^)...
    ollama pull qwen2.5-coder:14b
    if errorlevel 1 ( echo ERROR: qwen2.5-coder:14b pull failed. & pause & exit /b 1 )
)

ollama list | findstr "qwen2.5:32b" >nul 2>&1
if errorlevel 1 (
    echo ERROR: qwen2.5:32b not found. Pull it first:
    echo   ollama pull qwen2.5:32b
    pause & exit /b 1
)

echo.

REM ── Build 7B persona models ───────────────────────────────────────────────────
echo [1/5] Building guppy-fast  ^(qwen2.5:7b — fast butler^)...
ollama create guppy-fast -f Modelfile.guppy-fast
if errorlevel 1 ( echo ERROR: guppy-fast build failed. & pause & exit /b 1 )
echo       Done.
echo.

echo [2/5] Building vault-scraper  ^(qwen2.5:7b — seed vault extraction^)...
ollama create vault-scraper -f Modelfile.vault-scraper
if errorlevel 1 ( echo ERROR: vault-scraper build failed. & pause & exit /b 1 )
echo       Done.
echo.

REM ── Build 14B model ──────────────────────────────────────────────────────────
echo [3/5] Building merlin-code  ^(qwen2.5-coder:14b — code specialist^)...
ollama create merlin-code -f Modelfile.merlin-code
if errorlevel 1 ( echo ERROR: merlin-code build failed. & pause & exit /b 1 )
echo       Done.
echo.

REM ── Build 32B models ─────────────────────────────────────────────────────────
echo [4/5] Building guppy  ^(qwen2.5:32b — complex butler^)...
ollama create guppy -f Modelfile.guppy
if errorlevel 1 ( echo ERROR: guppy build failed. & pause & exit /b 1 )
echo       Done.
echo.

echo [5/5] Building merlin  ^(qwen2.5:32b — Socratic teaching^)...
ollama create merlin -f Modelfile.merlin
if errorlevel 1 ( echo ERROR: merlin build failed. & pause & exit /b 1 )
echo       Done.
echo.

echo ============================================
echo All 5 models rebuilt.
echo ============================================
echo.
ollama list
echo.
pause
