# kill_guppy.ps1 — Stop all Guppy processes and free port 8081

$killed = @()

# 1. Kill anything holding port 8081
$pids = netstat -ano 2>$null |
    Select-String ':\b8081\b' |
    ForEach-Object { ($_ -split '\s+')[-1] } |
    Where-Object { $_ -match '^\d+$' } |
    Select-Object -Unique

foreach ($p in $pids) {
    try {
        Stop-Process -Id $p -Force -ErrorAction Stop
        $killed += "PID $p (port 8081)"
    } catch {}
}

# 2. Kill Python processes running Guppy scripts
$guppyKeywords = @('guppy_api', 'server_runtime', 'launch.py', 'guppy_hub', 'guppy_launcher', 'hub_app')

Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    try {
        $cmd = (Get-WmiObject Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmd -and ($guppyKeywords | Where-Object { $cmd -like "*$_*" })) {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            $killed += "PID $($proc.Id) (python: $($cmd -replace '.+\\',''))"
        }
    } catch {}
}

if ($killed.Count -eq 0) {
    Write-Host "Nothing to kill — no Guppy processes found."
} else {
    Write-Host "Killed $($killed.Count) process(es):"
    $killed | ForEach-Object { Write-Host "  $_" }
}
