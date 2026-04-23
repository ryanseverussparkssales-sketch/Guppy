$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$port = 8081
$url  = "http://127.0.0.1:$port"

# ── 1. Start API if not already listening ─────────────────────────────────
$listening = netstat -ano | Select-String ":$port\s"
if (-not $listening) {
    Write-Host "Starting Guppy API on port $port..."
    $python = Join-Path $root '.venv\Scripts\python.exe'
    $launch = Join-Path $root 'src\guppy\cli\launch.py'
    Start-Process $python -ArgumentList $launch, 'api' -WorkingDirectory $root

    # Wait up to 10 s for the port to open
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep 1
        if (netstat -ano | Select-String ":$port\s") { $ready = $true; break }
    }
    if (-not $ready) { Write-Warning "API may not be ready yet — opening browser anyway." }
} else {
    Write-Host "API already running on port $port."
}

# ── 2. Open in dedicated app-mode browser window ──────────────────────────
$edgePaths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)

$browser = ($edgePaths + $chromePaths) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($browser) {
    Write-Host "Opening: $url"
    Start-Process $browser "--app=$url --window-size=1280,820 --window-position=80,60"
} else {
    Write-Host "Edge/Chrome not found — opening in default browser."
    Start-Process $url
}
