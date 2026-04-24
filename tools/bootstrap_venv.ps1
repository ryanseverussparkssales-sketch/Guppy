param(
    [switch]$Recreate,
    [switch]$Dev,
    [switch]$Optional
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $root ".venv"
$pythonExe = Join-Path $venvPath "Scripts/python.exe"

if ($Recreate -and (Test-Path $venvPath)) {
    Write-Host "[venv] Removing existing .venv" -ForegroundColor Cyan
    Remove-Item -Recurse -Force $venvPath
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "[venv] Creating .venv" -ForegroundColor Cyan
    py -3.12 -m venv $venvPath
}

Write-Host "[venv] Upgrading pip/setuptools/wheel" -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip setuptools wheel

Write-Host "[venv] Installing requirements.txt" -ForegroundColor Cyan
& $pythonExe -m pip install -r (Join-Path $root "requirements.txt")

if ($Dev -and (Test-Path (Join-Path $root "requirements-dev.txt"))) {
    Write-Host "[venv] Installing requirements-dev.txt" -ForegroundColor Cyan
    & $pythonExe -m pip install -r (Join-Path $root "requirements-dev.txt")
}

if ($Optional -and (Test-Path (Join-Path $root "requirements-optional.txt"))) {
    Write-Host "[venv] Installing requirements-optional.txt" -ForegroundColor Cyan
    & $pythonExe -m pip install -r (Join-Path $root "requirements-optional.txt")
}

Write-Host "[venv] Ready: $pythonExe" -ForegroundColor Green
