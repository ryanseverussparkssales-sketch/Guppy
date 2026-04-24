# Creates a desktop shortcut that opens the Guppy web UI in Edge app mode.
# Run once: powershell -ExecutionPolicy Bypass -File tools\create_webui_shortcut.ps1

$url     = "http://127.0.0.1:8081/index.html"
$edge    = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) {
    Write-Error "Microsoft Edge not found. Install Edge or adjust the path."
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnk     = Join-Path $desktop "Guppy Web UI.lnk"

$shell   = New-Object -ComObject WScript.Shell
$sc      = $shell.CreateShortcut($lnk)
$sc.TargetPath       = $edge
$sc.Arguments        = "--app=$url --window-size=1280,820 --window-position=80,60"
$sc.WorkingDirectory = Split-Path $edge
$sc.Description      = "Guppy Web UI"
$sc.Save()

Write-Host "Shortcut created: $lnk"
