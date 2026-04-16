@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
pushd "%ROOT%"
REM build_executable.bat — Build standalone Guppy.exe with PyInstaller
REM ====================================================================
REM NOTE: Requires an icon before shipping:
REM   Place a 256x256 .ico file at assets\guppy.ico and uncomment the
REM   --icon line below. The assets\ folder does not exist yet.
REM
REM Usage:
REM   build_executable.bat             — full clean build (standard profile)
REM   build_executable.bat --no-clean  — skip dist/build wipe (faster rebuilds)
REM   build_executable.bat --lean      — build lean profile via Guppy.spec
REM   build_executable.bat --light     — light profile build (no daemon/heavy deps)
REM   build_executable.bat --power     — power profile build (all features)
REM   build_executable.bat --ci        — no pause on completion (CI mode)

setlocal

set SKIP_CLEAN=0
set NO_PAUSE=0
set LEAN_BUILD=0
set ONEFILE_BUILD=0
set BUILD_PROFILE=standard

for %%A in (%*) do (
    if /i "%%~A"=="--no-clean" set SKIP_CLEAN=1
    if /i "%%~A"=="--ci" set NO_PAUSE=1
    if /i "%%~A"=="--lean" set LEAN_BUILD=1
    if /i "%%~A"=="--onefile" set ONEFILE_BUILD=1
    if /i "%%~A"=="--onedir" set ONEFILE_BUILD=0
    if /i "%%~A"=="--light" set BUILD_PROFILE=light
    if /i "%%~A"=="--power" set BUILD_PROFILE=power
)

REM Bake the runtime profile into the executable's default environment
set GUPPY_RUNTIME_PROFILE=%BUILD_PROFILE%

echo ============================================
if "%ONEFILE_BUILD%"=="1" (
    set BUILD_LAYOUT=onefile
) else (
    set BUILD_LAYOUT=onedir
)

echo Guppy AI - Executable Builder  [PROFILE: %BUILD_PROFILE%] [LAYOUT: %BUILD_LAYOUT%]
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
    if exist "guppy_launcher.spec" del "guppy_launcher.spec"
    echo.
)

REM Build executable
if "%LEAN_BUILD%"=="1" (
    echo Building Guppy executable (LEAN profile)...
    echo This mode reduces optional dependency collection for faster iteration.
    echo.
    set GUPPY_LEAN_BUILD=1
    %PYTHON% -m PyInstaller --noconfirm bin\Guppy.spec
) else (
    echo Building Guppy executable (profile: %BUILD_PROFILE%)...
    echo This may take 5-10 minutes...
    echo.
    if "%ONEFILE_BUILD%"=="1" (
        set BUILD_MODE_FLAG=--onefile
    ) else (
        set BUILD_MODE_FLAG=--onedir
    )

    %PYTHON% -m PyInstaller %BUILD_MODE_FLAG% ^
        --windowed ^
        --name "Guppy" ^
        --add-data "src\guppy\ui\theme.json;src\guppy\ui" ^
        --add-data "models;models" ^
        --add-data "web;web" ^
        --add-data "utils;utils" ^
        --add-data "ui;ui" ^
        --add-data "runtime;runtime" ^
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
        --hidden-import=src.guppy.memory.semantic ^
        --hidden-import=src.guppy.daemon.daemon ^
        --hidden-import=src.guppy.memory.memory ^
        --hidden-import=src.guppy.merlin.core ^
        --hidden-import=src.guppy.inference.router ^
        --hidden-import=src.guppy.tools.media ^
        --hidden-import=src.guppy.integrations.crm_voip ^
        --hidden-import=utils.hub_operator ^
        --hidden-import=utils.agent_perf ^
        --hidden-import=utils.session_logger ^
        --hidden-import=utils.operational_telemetry ^
        --hidden-import=utils.env_bootstrap ^
        --hidden-import=utils.heartbeat ^
        --hidden-import=utils.runtime_profile ^
        --hidden-import=utils.settings_dialog ^
        --hidden-import=utils.telemetry_window ^
        --hidden-import=utils.diagnostics_bundle ^
        --hidden-import=ui.components.status_strip ^
        --hidden-import=ui.components.timeline_panel ^
        --hidden-import=ui.components.startup_checklist ^
        --hidden-import=ui.components.sparkline ^
        --hidden-import=ui.components.command_palette ^
        --hidden-import=src.guppy.debug.console ^
        --hidden-import=src.guppy.ui.theme ^
        --hidden-import=psutil ^
        --hidden-import=pyperclip ^
        --hidden-import=keyboard ^
        --hidden-import=requests ^
        --hidden-import=apscheduler ^
        --hidden-import=spotipy ^
        --hidden-import=google.auth ^
        --hidden-import=google.oauth2 ^
        --hidden-import=googleapiclient ^
        --collect-all anthropic ^
        --collect-all PySide6 ^
        --collect-all faster_whisper ^
        --hidden-import=ui.launcher ^
        --hidden-import=ui.launcher.launcher_window ^
        --hidden-import=ui.launcher.views.assistant_view ^
        --hidden-import=ui.launcher.views.tools_view ^
        --hidden-import=ui.launcher.views.settings_view ^
        --hidden-import=ui.launcher.views.advanced_view ^
        --hidden-import=ui.launcher.views.models_view ^
        --hidden-import=ui.launcher.views.voices_view ^
        guppy_launcher.py
)

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
if "%ONEFILE_BUILD%"=="1" (
    echo Executable: dist\Guppy.exe
    for %%A in ("dist\Guppy.exe") do echo Size: %%~zA bytes
) else (
    echo Executable: dist\Guppy\Guppy.exe
    for %%A in ("dist\Guppy\Guppy.exe") do echo Size: %%~zA bytes
)
echo.
echo Run bin\validate_build.bat to smoke-test before distributing.
echo.
if "%NO_PAUSE%"=="1" exit /b 0
pause >nul
