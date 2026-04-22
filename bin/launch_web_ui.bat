@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
set "URL=http://127.0.0.1:8081"

title Guppy Web UI
cd /d "%ROOT%"

if not exist "static\index.html" (
    echo [web-ui] static build missing, attempting to build from web\ ...
    if exist "web\package.json" (
        where npm >nul 2>&1
        if errorlevel 1 (
            echo [web-ui] npm was not found. Install Node.js, then run "npm install" in web\.
            pause
            exit /b 1
        )
        pushd "web"
        if not exist "node_modules" (
            echo [web-ui] installing web dependencies...
            call npm install
            if errorlevel 1 (
                popd
                echo [web-ui] npm install failed.
                pause
                exit /b 1
            )
        )
        echo [web-ui] building static assets...
        call npm run build
        set "BUILD_EXIT=%ERRORLEVEL%"
        popd
        if not "%BUILD_EXIT%"=="0" (
            echo [web-ui] build failed with code %BUILD_EXIT%.
            pause
            exit /b %BUILD_EXIT%
        )
    ) else (
        echo [web-ui] web\package.json not found.
        pause
        exit /b 1
    )
)

netstat -ano | findstr ":8081 " >nul 2>&1
if errorlevel 1 (
    echo [web-ui] starting local API on port 8081...
    if exist ".venv\Scripts\python.exe" (
        start "Guppy API" ".venv\Scripts\python.exe" src\guppy\cli\launch.py api
    ) else (
        start "Guppy API" python src\guppy\cli\launch.py api
    )
)

start "" "%URL%"
echo [web-ui] opening %URL%
exit /b 0
