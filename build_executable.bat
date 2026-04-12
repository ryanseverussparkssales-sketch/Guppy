@echo off
REM build_executable.bat — Build standalone Guppy.exe with PyInstaller
REM ====================================================================
REM NOTE: Requires an icon before shipping:
REM   Place a 256x256 .ico file at assets\guppy.ico and uncomment the
REM   --icon line below. The assets\ folder does not exist yet.
REM
REM Usage:
REM   build_executable.bat           — full clean build
REM   build_executable.bat --no-clean — skip dist/build wipe (faster rebuilds)

setlocal

set SKIP_CLEAN=0
if /i "%1"=="--no-clean" set SKIP_CLEAN=1

echo ============================================
echo Guppy AI - Executable Builder
echo ============================================
echo.

REM Use venv python so all installed packages are available
set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

REM Check if PyInstaller is installed
%PYTHON% -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    %PYTHON% -m pip install pyinstaller
    echo.
)

REM Clean previous builds
if "%SKIP_CLEAN%"=="0" (
    echo Cleaning previous builds...
    if exist "dist"          rmdir /s /q "dist"
    if exist "build"         rmdir /s /q "build"
    if exist "Guppy.spec"    del "Guppy.spec"
    if exist "guppy_ui.spec" del "guppy_ui.spec"
    echo.
)

REM Build executable
echo Building Guppy executable...
echo This may take 5-10 minutes...
echo.

%PYTHON% -m PyInstaller --onefile ^
    --windowed ^
    --name "Guppy" ^
    --add-data "theme.json;." ^
    --add-data "models;models" ^
    --add-data "web;web" ^
    --add-data "utils;utils" ^
    --add-data "ui;ui" ^
    --hidden-import=anthropic ^
    --hidden-import=win32com.client ^
    --hidden-import=win11toast ^
    --hidden-import=sounddevice ^
    --hidden-import=soundfile ^
    --hidden-import=edge_tts ^
    --hidden-import=faster_whisper ^
    --hidden-import=PySide6.QtCore ^
    --hidden-import=PySide6.QtGui ^
    --hidden-import=PySide6.QtWidgets ^
    --hidden-import=PySide6.QtCharts ^
    --hidden-import=guppy_semantic_memory ^
    --hidden-import=guppy_daemon ^
    --hidden-import=guppy_memory ^
    --hidden-import=merlin_core ^
    --hidden-import=inference_router ^
    --hidden-import=media_tools ^
    --hidden-import=crm_voip_integrations ^
    --hidden-import=utils.hub_operator ^
    --hidden-import=utils.agent_perf ^
    --hidden-import=utils.session_logger ^
    --hidden-import=utils.env_bootstrap ^
    --hidden-import=utils.heartbeat ^
    --hidden-import=utils.telemetry_window ^
    --hidden-import=utils.diagnostics_bundle ^
    --hidden-import=ui.components.status_strip ^
    --hidden-import=ui.components.timeline_panel ^
    --hidden-import=ui.components.startup_checklist ^
    --hidden-import=ui.components.sparkline ^
    --hidden-import=ui.components.command_palette ^
    --hidden-import=debug_console ^
    --hidden-import=guppy_theme ^
    --hidden-import=psutil ^
    --hidden-import=pyperclip ^
    --hidden-import=keyboard ^
    --hidden-import=requests ^
    --hidden-import=APScheduler ^
    --hidden-import=spotipy ^
    --hidden-import=google.auth ^
    --hidden-import=google.oauth2 ^
    --hidden-import=googleapiclient ^
    --collect-all anthropic ^
    --collect-all PySide6 ^
    --collect-all faster_whisper ^
    guppy_ui.py

REM Uncomment once assets\guppy.ico exists:
REM     --icon=assets\guppy.ico ^

if errorlevel 1 (
    echo.
    echo BUILD FAILED. Check errors above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build Complete!
echo ============================================
echo.
echo Executable: dist\Guppy.exe
for %%A in ("dist\Guppy.exe") do echo Size: %%~zA bytes
echo.
echo Run validate_build.bat to smoke-test before distributing.
echo.
pause >nul
