# Comprehensive Guppy Setup & Diagnostic
# This script checks prerequisites, starts services, and verifies everything works

param(
    [switch]$StartServices = $false,
    [switch]$Quick = $false
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== GUPPY SETUP & DIAGNOSTIC ===" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot" -ForegroundColor Gray
Write-Host ""

# 1. Check Python
Write-Host "1. Checking Python Installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ $pythonVersion" -ForegroundColor Green
    [version]$ver = $pythonVersion -replace 'Python\s+', ''
    if ($ver -lt [version]"3.12") {
        Write-Host "⚠️  Python 3.12+ required (current: $ver)" -ForegroundColor Red
    }
} else {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
}

# 2. Check virtual environment
Write-Host "`n2. Checking Virtual Environment..." -ForegroundColor Yellow
$venvPath = Join-Path $repoRoot ".venv"
if (Test-Path $venvPath) {
    Write-Host "✅ Virtual environment found at .venv" -ForegroundColor Green
    $activateScript = Join-Path $venvPath "Scripts\activate.ps1"
    if (Test-Path $activateScript) {
        Write-Host "   Ready to activate" -ForegroundColor Gray
    }
} else {
    Write-Host "❌ Virtual environment not found. Run: python -m venv .venv" -ForegroundColor Red
}

# 3. Check Ollama
Write-Host "`n3. Checking Ollama Service..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Ollama is running on http://127.0.0.1:11434" -ForegroundColor Green
        $ollamaRunning = $true

        # Parse models
        try {
            $models = $response.Content | ConvertFrom-Json
            if ($models.models) {
                Write-Host "   Available models:" -ForegroundColor Gray
                foreach ($model in $models.models) {
                    Write-Host "   - $($model.name)" -ForegroundColor Gray
                }
            }
        } catch {
            Write-Host "   (Could not parse model list)" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "❌ Ollama not responding on :11434" -ForegroundColor Red
    Write-Host "   Start Ollama, or check alternative LLM setup" -ForegroundColor Gray
}

# 4. Check for alternative LLM setups
if (-not $ollamaRunning) {
    Write-Host "`n4. Checking for Alternative LLM Setups..." -ForegroundColor Yellow

    $lmStudioPort = 1234
    $openWebUIPort = 8000
    $anythingLLMPort = 3001

    $alternatives = @(
        @{ Name = "LMStudio"; Port = $lmStudioPort; URL = "http://127.0.0.1:$lmStudioPort" }
        @{ Name = "Open WebUI"; Port = $openWebUIPort; URL = "http://127.0.0.1:$openWebUIPort" }
        @{ Name = "AnythingLLM"; Port = $anythingLLMPort; URL = "http://127.0.0.1:$anythingLLMPort" }
    )

    foreach ($alt in $alternatives) {
        try {
            $response = Invoke-WebRequest -Uri $alt.URL -TimeoutSec 1 -ErrorAction SilentlyContinue
            Write-Host "✅ $($alt.Name) detected on port $($alt.Port)" -ForegroundColor Green
        } catch {
            Write-Host "   $($alt.Name) not responding on port $($alt.Port)" -ForegroundColor Gray
        }
    }
}

# 5. Check Guppy API
Write-Host "`n5. Checking Guppy API..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "✅ Guppy API is running on :8000" -ForegroundColor Green
} catch {
    Write-Host "❌ Guppy API not responding on :8000 (expected during initial setup)" -ForegroundColor Yellow
}

# 6. Check dependencies
Write-Host "`n6. Checking Key Python Dependencies..." -ForegroundColor Yellow
$deps = @("fastapi", "sqlalchemy", "pydantic", "httpx")
foreach ($dep in $deps) {
    $check = python -c "import $dep" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ $dep" -ForegroundColor Green
    } else {
        Write-Host "⚠️  $dep (may need to run: pip install -e .)" -ForegroundColor Yellow
    }
}

# 7. Show next steps
Write-Host "`n=== NEXT STEPS ===" -ForegroundColor Cyan

if (-not $ollamaRunning) {
    Write-Host "`n📋 OPTION A: Start Ollama (Recommended)" -ForegroundColor Yellow
    Write-Host "  1. Open Windows Terminal / PowerShell"
    Write-Host "  2. Run: ollama serve" -ForegroundColor White
    Write-Host "  3. Keep terminal open (Ollama listens on :11434)"
    Write-Host ""
    Write-Host "📋 OPTION B: Use Alternative LLM (LMStudio, Open WebUI, etc.)" -ForegroundColor Yellow
    Write-Host "  1. Start your preferred LLM service" -ForegroundColor White
    Write-Host "  2. Update Guppy config to point to the right endpoint" -ForegroundColor White
}

Write-Host "`n📋 Start Guppy API:" -ForegroundColor Yellow
Write-Host "  1. Activate venv: .venv\Scripts\activate" -ForegroundColor White
Write-Host "  2. Run API: python -m src.guppy.cli.launch api --dev" -ForegroundColor White
Write-Host "  3. Or run Web Hub: python -m src.guppy.cli.launch hub --dev" -ForegroundColor White

Write-Host "`n📋 Access Web UI:" -ForegroundColor Yellow
Write-Host "  http://localhost:3000 (if Web UI is running)" -ForegroundColor White

Write-Host "`n📋 Environment Variables:" -ForegroundColor Yellow
Write-Host "  GUPPY_DEV_MODE=1         (enables debug logging)" -ForegroundColor Gray
Write-Host "  GUPPY_JWT_SECRET=<value> (for JWT auth, optional)" -ForegroundColor Gray

if ($StartServices) {
    Write-Host "`n=== STARTING SERVICES ===" -ForegroundColor Cyan

    # Activate venv
    $activateScript = Join-Path $repoRoot ".venv\Scripts\activate.ps1"
    if (Test-Path $activateScript) {
        Write-Host "Activating venv..." -ForegroundColor Yellow
        & $activateScript
    }

    # Start API
    Write-Host "Starting Guppy API on :8000..." -ForegroundColor Yellow
    $env:GUPPY_DEV_MODE = "1"
    python -m src.guppy.cli.launch api --dev
}

Write-Host "`n" -ForegroundColor Gray
Write-Host "For more details, see: $repoRoot\CLAUDE.md" -ForegroundColor Gray
