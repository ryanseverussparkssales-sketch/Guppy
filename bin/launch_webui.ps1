$log = Join-Path $PSScriptRoot 'launch_webui.log'
"[$(Get-Date -f 'HH:mm:ss')] Starting" | Out-File $log

try {
    $root = Split-Path $PSScriptRoot -Parent
    "[$(Get-Date -f 'HH:mm:ss')] root=$root" | Add-Content $log

    $port = 8081
    $url  = "http://127.0.0.1:$port"

    # ── 1. Start API if not already listening ───────────────────────────
    $listening = netstat -ano 2>$null | Select-String ":$port\s"
    "[$(Get-Date -f 'HH:mm:ss')] listening=$($null -ne $listening)" | Add-Content $log

    if (-not $listening) {
        $python = Join-Path $root '.venv\Scripts\python.exe'
        "[$(Get-Date -f 'HH:mm:ss')] python path=$python exists=$(Test-Path $python)" | Add-Content $log

        if (Test-Path $python) {
            $launch = Join-Path $root 'src\guppy\cli\launch.py'
            Start-Process $python -ArgumentList $launch, 'api' -WorkingDirectory $root
            "[$(Get-Date -f 'HH:mm:ss')] API started, waiting..." | Add-Content $log

            for ($i = 0; $i -lt 10; $i++) {
                Start-Sleep 1
                if (netstat -ano 2>$null | Select-String ":$port\s") { break }
            }
        } else {
            "[$(Get-Date -f 'HH:mm:ss')] ERROR: python not found at $python" | Add-Content $log
        }
    }

    # ── 2. Open browser ─────────────────────────────────────────────────
    $candidates = @(
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    $browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    "[$(Get-Date -f 'HH:mm:ss')] browser=$browser" | Add-Content $log

    if ($browser) {
        Start-Process $browser -ArgumentList "--app=$url", "--window-size=1280,820", "--window-position=80,60"
    } else {
        Start-Process $url
    }
    "[$(Get-Date -f 'HH:mm:ss')] Done" | Add-Content $log
} catch {
    "[$(Get-Date -f 'HH:mm:ss')] EXCEPTION: $_" | Add-Content $log
    Write-Host "Error: $_"
    Read-Host "Press Enter to close"
}
