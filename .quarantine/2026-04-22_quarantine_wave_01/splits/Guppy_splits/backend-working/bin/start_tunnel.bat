@echo off
REM start_tunnel.bat — Start Cloudflare Tunnel for Guppy API
REM ========================================================
REM
REM This script sets up a Cloudflare Tunnel to expose the Guppy API
REM server to the internet securely.
REM
REM Requirements:
REM - cloudflared installed (winget install cloudflared)
REM - Cloudflare account with domain
REM - Tunnel created and configured in Cloudflare dashboard
REM
REM Setup steps:
REM 1. Install cloudflared: winget install cloudflared
REM 2. Login: cloudflared tunnel login
REM 3. Create tunnel: cloudflared tunnel create guppy
REM 4. Configure DNS: Set CNAME record for your subdomain
REM 5. Update TUNNEL_ID below with your tunnel UUID

echo Cloudflare Tunnel Setup for Guppy API
echo ======================================
echo.

REM Configuration - Update these values
set TUNNEL_NAME=guppy
set TUNNEL_ID=your-tunnel-uuid-here
set LOCAL_HOST=localhost
set LOCAL_PORT=8081

REM Resolve cloudflared — prefer bundled binary in bin\
set CF_BIN=%~dp0cloudflared.exe
if not exist "%CF_BIN%" set CF_BIN=cloudflared
"%CF_BIN%" version >nul 2>&1
if errorlevel 1 (
    echo ERROR: cloudflared not found at %CF_BIN%
    echo Download it or run: winget install Cloudflare.cloudflared
    pause
    exit /b 1
)

REM Load TUNNEL_ID from .env if not already set
if "%TUNNEL_ID%"=="your-tunnel-uuid-here" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\.env") do (
        if "%%A"=="CLOUDFLARE_TUNNEL_ID" set TUNNEL_ID=%%B
        if "%%A"=="CLOUDFLARE_HOSTNAME"  set TUNNEL_HOSTNAME=%%B
    )
)

REM Abort if tunnel ID still placeholder
if "%TUNNEL_ID%"=="your-tunnel-uuid-here" (
    echo ERROR: TUNNEL_ID not configured.
    echo Set CLOUDFLARE_TUNNEL_ID in .env or run:
    echo   bin\cloudflared.exe tunnel create %TUNNEL_NAME%
    echo Then copy the UUID into .env as CLOUDFLARE_TUNNEL_ID
    pause
    exit /b 1
)

REM Check if tunnel exists
"%CF_BIN%" tunnel list | findstr "%TUNNEL_ID%" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Tunnel '%TUNNEL_ID%' not found in Cloudflare account.
    echo Login first with:  bin\cloudflared.exe tunnel login
    echo Then create with:  bin\cloudflared.exe tunnel create %TUNNEL_NAME%
    pause
    exit /b 1
)

echo Starting Cloudflare Tunnel...
echo Tunnel Name: %TUNNEL_NAME%
echo Tunnel ID: %TUNNEL_ID%
echo Local Target: %LOCAL_HOST%:%LOCAL_PORT%
echo.
echo IMPORTANT: Make sure the Guppy API server is running first!
echo Run 'bin\launch_api.bat' in another terminal.
echo.
echo Press Ctrl+C to stop the tunnel
echo.

REM Start the tunnel
"%CF_BIN%" tunnel run --url http://%LOCAL_HOST%:%LOCAL_PORT% %TUNNEL_ID%

pause