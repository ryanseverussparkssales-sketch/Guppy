@echo off
REM build_executable.bat — Build standalone Guppy.exe with PyInstaller
REM ====================================================================
REM NOTE: Requires an icon before shipping:
REM   Place a 256x256 .ico file at assets\guppy.ico and uncomment the
REM   --icon line below. The assets\ folder does not exist yet.

echo ============================================
echo Guppy AI - Executable Builder
echo ============================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist"        rmdir /s /q "dist"
if exist "build"       rmdir /s /q "build"
if exist "guppy_ui.spec" del "guppy_ui.spec"
echo.

REM Build executable
echo Building Guppy executable...
echo This may take 5-10 minutes...
echo.

pyinstaller --onefile ^
    --windowed ^
    --name "Guppy" ^
    --add-data "theme.json;." ^
    --add-data "models;models" ^
    --add-data "web;web" ^
    --hidden-import=anthropic ^
    --hidden-import=win32com.client ^
    --hidden-import=sounddevice ^
    --hidden-import=soundfile ^
    --hidden-import=edge_tts ^
    --hidden-import=faster_whisper ^
    --hidden-import=PySide6.QtCore ^
    --hidden-import=PySide6.QtGui ^
    --hidden-import=PySide6.QtWidgets ^
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
echo Testing executable...
start "" "dist\Guppy.exe"
echo.
pause >nul
