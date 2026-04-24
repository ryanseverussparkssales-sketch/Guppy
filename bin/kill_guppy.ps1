param()
# kill_guppy.ps1 - Stop all Guppy processes and free port 8081

$killed = [System.Collections.Generic.List[string]]::new()

# 1. Kill anything holding port 8081
$portPids = netstat -ano 2>$null |
    Select-String ':8081' |
    ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] } |
    Where-Object { $_ -match '^\d+$' } |
    Select-Object -Unique

foreach ($p in $portPids) {
    try {
        Stop-Process -Id ([int]$p) -Force -ErrorAction Stop
        $killed.Add("PID $p (port 8081)")
    } catch { }
}

# 2. Kill Python processes running Guppy scripts
$keywords = 'guppy_api','server_runtime','launch.py','guppy_hub','guppy_launcher','hub_app'

Get-Process -Name python,pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    $id  = $_.Id
    $wmi = Get-WmiObject Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if (-not $wmi) { return }
    $cmd = $wmi.CommandLine
    $match = $keywords | Where-Object { $cmd -like "*$_*" } | Select-Object -First 1
    if ($match) {
        try {
            Stop-Process -Id $id -Force -ErrorAction Stop
            $killed.Add("PID $id (python: $match)")
        } catch { }
    }
}

if ($killed.Count -eq 0) {
    Write-Host 'Nothing to kill - no Guppy processes found.'
} else {
    Write-Host "Killed $($killed.Count) process(es):"
    foreach ($entry in $killed) {
        Write-Host "  $entry"
    }
}
