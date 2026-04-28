# diagnose_tests.ps1 — interrupt hung pytest, identify failures, save log for Claude
# Run: .\diagnose_tests.ps1

$ErrorActionPreference = "Continue"
$Root = "C:\Users\Ryan\Guppy"
Set-Location $Root

Write-Host "[1/5] Killing any running pytest processes..." -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -match "python|pytest" } | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction Stop; Write-Host "  killed PID $($_.Id) ($($_.ProcessName))" }
    catch { Write-Host "  could not kill PID $($_.Id): $_" }
}

Write-Host "[2/5] Removing corrupted duplicate test file..." -ForegroundColor Yellow
$corrupted = "tests\unit\test_stt_providers_fixed.py"
if (Test-Path $corrupted) {
    Remove-Item $corrupted -Force
    Write-Host "  removed $corrupted"
} else {
    Write-Host "  $corrupted already gone"
}

Write-Host "[3/5] Ensuring pytest-timeout is installed..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m pip install pytest-timeout --quiet 2>&1 | Out-Null
Write-Host "  done"

Write-Host "[4/5] Running pytest with 15s per-test timeout, output -> diagnose_tests.log" -ForegroundColor Yellow
$logfile = "diagnose_tests.log"
& ".venv\Scripts\python.exe" -m pytest tests/unit `
    --timeout=15 `
    --timeout-method=thread `
    -q `
    --tb=short `
    --no-header `
    -rf `
    --no-cov `
    2>&1 | Tee-Object -FilePath $logfile

Write-Host ""
Write-Host "[5/5] Summary of failures:" -ForegroundColor Yellow
Write-Host ""
Select-String -Path $logfile -Pattern "FAILED|TIMEOUT|short test summary|passed|failed" | ForEach-Object {
    Write-Host $_.Line
}

Write-Host ""
Write-Host "Done. Full log: $Root\$logfile" -ForegroundColor Green
Write-Host "Paste the failure summary into Claude to continue." -ForegroundColor Green
