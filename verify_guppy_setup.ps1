#!/usr/bin/env pwsh
<#
.SYNOPSIS
Verify Guppy setup - Check ports, API endpoints, and frontend/backend connectivity

.DESCRIPTION
This utility checks:
- Is backend API running on port 8081?
- Is web UI running on port 3003?
- Can they communicate?
- Are endpoints available?
- What's the current configuration?
#>

param(
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================"
Write-Host "  GUPPY SETUP VERIFICATION"
Write-Host "============================================================"
Write-Host ""

# Color helpers
function Write-Success { Write-Host -ForegroundColor Green "[OK]     $args" }
function Write-Error-Msg { Write-Host -ForegroundColor Red "[ERROR]  $args" }
function Write-Warn { Write-Host -ForegroundColor Yellow "[WARN]   $args" }
function Write-Info { Write-Host -ForegroundColor Cyan "[INFO]   $args" }

$allOk = $true

# ============================================================================
# 1. Check Backend API (port 8081)
# ============================================================================
Write-Host ""
Write-Info "Checking Backend API (port 8081)..."

$apiPort = 8081
$apiUrl = "http://127.0.0.1:$apiPort"

try {
    $response = Invoke-WebRequest -Uri $apiUrl -TimeoutSec 3 -ErrorAction Stop
    Write-Success "Backend API is responding ($($response.StatusCode))"

    # Try to get status
    try {
        $status = Invoke-WebRequest -Uri "$apiUrl/api/status" -TimeoutSec 3 -ErrorAction Stop
        Write-Success "API /api/status endpoint is available"
    } catch {
        Write-Warn "API /api/status endpoint not found (404) - may be in limited mode"
    }
} catch {
    Write-Error-Msg "Backend API is NOT responding on port $apiPort"
    Write-Warn "Make sure backend is started: python -m guppy.cli.launch api"
    $allOk = $false
}

# ============================================================================
# 2. Check Web UI (port 3003)
# ============================================================================
Write-Host ""
Write-Info "Checking Web UI (port 3003)..."

$webPort = 3003
$webUrl = "http://127.0.0.1:$webPort"

try {
    $response = Invoke-WebRequest -Uri $webUrl -TimeoutSec 3 -ErrorAction Stop
    Write-Success "Web UI is responding on port $webPort ($($response.StatusCode))"
} catch {
    Write-Error-Msg "Web UI is NOT responding on port $webPort"
    Write-Warn "Make sure web UI dev server is started: cd web && npm run dev"
    $allOk = $false
}

# ============================================================================
# 3. Check Network Connectivity
# ============================================================================
Write-Host ""
Write-Info "Checking connectivity between services..."

if ($allOk) {
    try {
        # Try from frontend to backend (this is what matters for the app)
        $testUrl = "$apiUrl/api/instances"
        $response = Invoke-WebRequest -Uri $testUrl -TimeoutSec 3 -ErrorAction SilentlyContinue

        if ($response.StatusCode -eq 200) {
            Write-Success "Frontend can reach backend API endpoints"
        } elseif ($response.StatusCode -eq 404) {
            Write-Warn "Backend API is reachable but endpoint returns 404"
            Write-Warn "This may indicate API is in limited/readonly mode"
        } else {
            Write-Warn "Backend API returned status $($response.StatusCode)"
        }
    } catch {
        Write-Error-Msg "Frontend cannot reach backend API at $apiUrl"
        $allOk = $false
    }
}

# ============================================================================
# 4. Check Environment Variables
# ============================================================================
Write-Host ""
Write-Info "Checking configuration..."

$apiUrlEnv = [Environment]::GetEnvironmentVariable("VITE_API_URL")
if ($apiUrlEnv) {
    Write-Info "VITE_API_URL environment variable: $apiUrlEnv"
} else {
    Write-Info "VITE_API_URL not set (using default: $apiUrl)"
}

$devMode = [Environment]::GetEnvironmentVariable("GUPPY_DEV_MODE")
if ($devMode) {
    Write-Info "GUPPY_DEV_MODE: $devMode"
}

# ============================================================================
# 5. Check Running Processes
# ============================================================================
Write-Host ""
Write-Info "Checking running processes..."

$pythonProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq "python" }
if ($pythonProcess) {
    Write-Success "Python process is running (backend API)"
} else {
    Write-Warn "No Python process found (backend API may not be running)"
}

$nodeProcess = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcess) {
    Write-Success "Node process is running (web UI dev server)"
} else {
    Write-Warn "No Node process found (web UI dev server may not be running)"
}

# ============================================================================
# 6. Summary
# ============================================================================
Write-Host ""
Write-Host "============================================================"
Write-Host "  VERIFICATION SUMMARY"
Write-Host "============================================================"
Write-Host ""

if ($allOk) {
    Write-Success "All checks passed! Your Guppy setup is working."
    Write-Host ""
    Write-Host "  Backend API:  $apiUrl"
    Write-Host "  Web UI:       $webUrl"
    Write-Host ""
    Write-Host "  Open http://127.0.0.1:3003 in your browser"
    Write-Host ""
} else {
    Write-Error-Msg "Setup verification failed. Check the errors above."
    Write-Host ""
    Write-Host "Quick start:"
    Write-Host "  1. Open Terminal 1: python -m guppy.cli.launch api"
    Write-Host "  2. Open Terminal 2: cd web && npm run dev"
    Write-Host "  3. Then run this script again"
    Write-Host ""
}

Write-Host "============================================================"
Write-Host ""

if (-not $allOk) {
    exit 1
}
