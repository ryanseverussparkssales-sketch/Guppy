# Register Guppy tray as a Windows startup item via Task Scheduler.
# Run once as the current user — no admin rights required.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\register_tray_startup.ps1
#
# To remove:
#   Unregister-ScheduledTask -TaskName "GuppyTray" -Confirm:$false

$ErrorActionPreference = "Stop"

$repoRoot  = Split-Path -Parent $PSScriptRoot
$taskName  = "GuppyTray"

# venv may live in the worktree or in the parent Guppy repo — try both
$pythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $pythonw = "C:\Users\Ryan\Guppy\.venv\Scripts\pythonw.exe"
}
if (-not (Test-Path $pythonw)) {
    Write-Error "pythonw.exe not found — expected at $pythonw"
    exit 1
}

$launchPy  = Join-Path $repoRoot "src\guppy\cli\launch.py"

if (-not (Test-Path $launchPy)) {
    Write-Error "launch.py not found at $launchPy"
    exit 1
}

# Remove stale registration if it exists
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed existing '$taskName' task."
}

$action  = New-ScheduledTaskAction `
    -Execute  $pythonw `
    -Argument "`"$launchPy`" tray" `
    -WorkingDirectory $repoRoot

# Trigger: at log-on for this user only
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances  IgnoreNew `
    -RestartCount       3 `
    -RestartInterval    (New-TimeSpan -Minutes 1)

$principal = New-ScheduledTaskPrincipal `
    -UserId    $env:USERNAME `
    -LogonType Interactive `
    -RunLevel  Limited

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "OK - $taskName registered. Tray will launch automatically at login."
Write-Host "To start it now: Start-ScheduledTask -TaskName $taskName"
