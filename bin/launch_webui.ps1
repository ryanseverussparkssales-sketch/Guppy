$log  = Join-Path $PSScriptRoot 'launch_webui.log'
"[$(Get-Date -f 'HH:mm:ss')] script started" | Out-File $log -Encoding utf8
$root   = Split-Path $PSScriptRoot -Parent
$port   = 8081
$url    = "http://127.0.0.1:$port/index.html"
$health = "http://127.0.0.1:$port/health"

function Test-ApiReady {
    try {
        $r = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $r.StatusCode -lt 500
    } catch { return $false }
}

# ── 1. Start API if it isn't responding ───────────────────────────────────
if (-not (Test-ApiReady)) {
    Write-Host "API not running — starting..."
    $python = Join-Path $root '.venv\Scripts\python.exe'
    $launch = Join-Path $root 'src\guppy\cli\launch.py'

    if (-not (Test-Path $python)) {
        Write-Host "ERROR: venv not found at $python"
        Read-Host "Press Enter to close"
        exit 1
    }

    # Visible window so startup errors are readable
    Start-Process $python -ArgumentList "`"$launch`"", 'api' -WorkingDirectory $root

    Write-Host "Waiting for API..." -NoNewline
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep 1
        Write-Host "." -NoNewline
        if (Test-ApiReady) { $ready = $true; break }
    }
    Write-Host ""
    if (-not $ready) {
        Write-Host "WARNING: API did not respond in 15 s — opening browser anyway."
    }
} else {
    Write-Host "API already running."
}

# ── 2. Open in dedicated app-mode window ─────────────────────────────────
$candidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host "Opening $url ..."
if ($browser) {
    "[$(Get-Date -f 'HH:mm:ss')] launching browser: $browser" | Add-Content $log -Encoding utf8
    Start-Process $browser -ArgumentList "--app=$url", "--window-size=1280,820", "--window-position=80,60" -WindowStyle Normal
} else {
    "[$(Get-Date -f 'HH:mm:ss')] no Edge/Chrome found, using Start-Process url" | Add-Content $log -Encoding utf8
    Start-Process $url -WindowStyle Normal
}
"[$(Get-Date -f 'HH:mm:ss')] done" | Add-Content $log -Encoding utf8
