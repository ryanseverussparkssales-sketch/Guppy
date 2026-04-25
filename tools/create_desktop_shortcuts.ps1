# create_desktop_shortcuts.ps1
# Run: powershell -ExecutionPolicy Bypass -File tools\create_desktop_shortcuts.ps1

$Root     = (Resolve-Path "$PSScriptRoot\..").Path
$RootFwd  = $Root.Replace('\', '/')
$Desktop  = [Environment]::GetFolderPath("Desktop")
$GuppyDir = Join-Path $Desktop "Guppy"
$WShell   = New-Object -ComObject WScript.Shell

$Edge    = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$Python  = Join-Path $Root ".venv\Scripts\pythonw.exe"
$PythonC = Join-Path $Root ".venv\Scripts\python.exe"
$PS      = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Cmd     = "$env:SystemRoot\System32\cmd.exe"

if (-not (Test-Path $GuppyDir)) { New-Item -ItemType Directory -Path $GuppyDir | Out-Null }

function Set-Shortcut([string]$LnkPath, [string]$Target, [string]$Lnk_Args, [string]$Work, [string]$Icon) {
    $s = $WShell.CreateShortcut($LnkPath)
    $s.TargetPath       = $Target
    $s.Arguments        = $Lnk_Args
    $s.WorkingDirectory = $Work
    if ($Icon) { $s.IconLocation = $Icon }
    $s.Save()
}

Write-Host "Building shortcuts in $GuppyDir`n"

# ── 1. Guppy Web UI ──────────────────────────────────────────────────────────
# Hidden PS script: start API if not up, then open Edge
$ps1 = "$Root\bin\_launch_webui.ps1"
@"
`$busy = netstat -ano | Select-String ':8081 '
if (-not `$busy) {
    Start-Process '$PythonC' -ArgumentList '"$Root\src\guppy\cli\launch.py" api' -WorkingDirectory '$Root' -WindowStyle Minimized
    Start-Sleep -Seconds 4
}
Start-Process '$Edge' '--app=http://127.0.0.1:8081/index.html --window-size=1280,900'
"@ | Set-Content $ps1 -Encoding UTF8

Set-Shortcut `
    -LnkPath  "$GuppyDir\Guppy Web UI.lnk" `
    -Target   $PS `
    -Lnk_Args "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ps1`"" `
    -Work     $Root `
    -Icon     "$Edge,0"
Write-Host "  [OK] Guppy Web UI"

# ── 2. Guppy Desktop UI ──────────────────────────────────────────────────────
Set-Shortcut `
    -LnkPath  "$GuppyDir\Guppy Desktop.lnk" `
    -Target   $Python `
    -Lnk_Args "`"$Root\guppy_launcher.py`"" `
    -Work     $Root `
    -Icon     "$Python,0"
Write-Host "  [OK] Guppy Desktop"

# ── 3. Quick Chat (standalone HTML → Ollama directly) ────────────────────────
$chatFile = "$Root\web\standalone_chat.html"
$chatUrl  = "file:///" + $chatFile.Replace('\','/')

Set-Shortcut `
    -LnkPath  "$GuppyDir\Quick Chat (Local).lnk" `
    -Target   $Edge `
    -Lnk_Args "--new-window --app=$chatUrl --window-size=960,820" `
    -Work     $Root `
    -Icon     "$Edge,0"
Write-Host "  [OK] Quick Chat (Local)"

# ── 4. Debug Dashboard ────────────────────────────────────────────────────────
$debugFile = "$Root\web\debug.html"
$debugUrl  = "file:///" + $debugFile.Replace('\','/')

Set-Shortcut `
    -LnkPath  "$GuppyDir\Guppy Debug.lnk" `
    -Target   $Edge `
    -Lnk_Args "--new-window --app=$debugUrl --window-size=1100,800" `
    -Work     $Root `
    -Icon     "$Edge,0"
Write-Host "  [OK] Guppy Debug"

# ── 5. Terminal Chat ──────────────────────────────────────────────────────────
Set-Shortcut `
    -LnkPath  "$GuppyDir\Terminal Chat.lnk" `
    -Target   $Cmd `
    -Lnk_Args "/k `"`"$PythonC`" `"$Root\bin\vllm_chat.py`"`"" `
    -Work     $Root `
    -Icon     "$Cmd,0"
Write-Host "  [OK] Terminal Chat"

# ── 6. Kill Guppy ─────────────────────────────────────────────────────────────
Set-Shortcut `
    -LnkPath  "$GuppyDir\Kill Guppy.lnk" `
    -Target   $PS `
    -Lnk_Args "-ExecutionPolicy Bypass -File `"$Root\bin\kill_guppy.ps1`"" `
    -Work     $Root `
    -Icon     "$env:SystemRoot\System32\shell32.dll,131"
Write-Host "  [OK] Kill Guppy"

Write-Host "`nDone."
