# Complete Guppy Setup & Desktop Integration
# Run this ONCE to set everything up

param(
    [switch]$SkipShortcuts = $false,
    [switch]$Force = $false
)

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       GUPPY COMPLETE SETUP & DESKTOP INTEGRATION          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Prerequisites
Write-Host "Step 1: Checking Prerequisites..." -ForegroundColor Yellow
Write-Host ""

$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.12+" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green

# Step 2: Check/Create Virtual Environment
Write-Host ""
Write-Host "Step 2: Setting up Virtual Environment..." -ForegroundColor Yellow
Write-Host ""

$venvPath = Join-Path $repoRoot ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Gray
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

# Activate venv
$activateScript = Join-Path $venvPath "Scripts\activate.ps1"
& $activateScript

# Step 3: Install Dependencies
Write-Host ""
Write-Host "Step 3: Installing Dependencies..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Installing Guppy package and dependencies..." -ForegroundColor Gray
pip install -q -e $repoRoot
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some dependencies may have failed (non-critical)" -ForegroundColor Yellow
}

# Step 4: Create Desktop Shortcuts
if (-not $SkipShortcuts) {
    Write-Host ""
    Write-Host "Step 4: Creating Desktop Shortcuts..." -ForegroundColor Yellow
    Write-Host ""

    $createShortcutsScript = Join-Path $repoRoot "tools\create_desktop_shortcuts.ps1"
    if (Test-Path $createShortcutsScript) {
        $args = if ($Force) { "-Force" } else { "" }
        & $createShortcutsScript $args
    } else {
        Write-Host "⚠️  Shortcut script not found (non-critical)" -ForegroundColor Yellow
    }
}

# Step 5: Diagnostics
Write-Host ""
Write-Host "Step 5: Running Diagnostics..." -ForegroundColor Yellow
Write-Host ""

$diagScript = Join-Path $repoRoot "tools\diagnose_and_setup.ps1"
if (Test-Path $diagScript) {
    & $diagScript -Quick
} else {
    Write-Host "⚠️  Diagnostic script not found" -ForegroundColor Yellow
}

# Final Summary
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  SETUP COMPLETE! 🎉                        ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  Start Ollama (in a new terminal):" -ForegroundColor White
Write-Host "    ollama serve" -ForegroundColor Gray
Write-Host ""
Write-Host "2️⃣  Click a shortcut on your Desktop:" -ForegroundColor White
Write-Host "    • Guppy - API Server (backend only)" -ForegroundColor Gray
Write-Host "    • Guppy - Web UI (API + web interface)" -ForegroundColor Gray
Write-Host "    • Guppy - Desktop Launcher (native app)" -ForegroundColor Gray
Write-Host ""
Write-Host "3️⃣  Open browser to:" -ForegroundColor White
Write-Host "    http://localhost:3000 (for Web UI)" -ForegroundColor Gray
Write-Host ""
Write-Host "TROUBLESHOOTING:" -ForegroundColor Yellow
Write-Host "  • See TOOLS.md for detailed setup by LLM provider" -ForegroundColor Gray
Write-Host "  • Run: powershell -File tools/diagnose_and_setup.ps1" -ForegroundColor Gray
Write-Host ""
