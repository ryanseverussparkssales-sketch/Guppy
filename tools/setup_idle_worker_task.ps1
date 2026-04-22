param(
    [string]$TaskName = "Guppy Idle Worker",
    [switch]$RunNow
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $workspace "bin\launch_idle_worker.bat"

if (-not (Test-Path $launcher)) {
    throw "Launcher not found: $launcher"
}

$taskCommand = "cmd.exe /c `"$launcher`""
$startupFolder = [Environment]::GetFolderPath("Startup")
$startupLink = Join-Path $startupFolder "Guppy Idle Worker.lnk"

function Set-StartupShortcut {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupLink)
    $shortcut.TargetPath = "cmd.exe"
    $shortcut.Arguments = "/c `"$launcher`""
    $shortcut.WorkingDirectory = $workspace
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Start Guppy idle worker at user logon"
    $shortcut.Save()
}

$mode = "task_scheduler"
schtasks /Create /TN $TaskName /SC ONLOGON /TR $taskCommand /RL LIMITED /IT /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    $mode = "startup_shortcut"
    Set-StartupShortcut
}

if ($RunNow) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$launcher`"" -WorkingDirectory $workspace -WindowStyle Minimized
}

if ($mode -eq "task_scheduler") {
    schtasks /Query /TN $TaskName /V /FO LIST
} else {
    [pscustomobject]@{
        mode = $mode
        startup_link = $startupLink
        launcher = $launcher
    } | ConvertTo-Json -Depth 3
}
