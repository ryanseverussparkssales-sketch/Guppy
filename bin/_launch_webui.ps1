$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

# Start API if nothing is already listening on 8081
$busy = netstat -ano | Select-String ':8081 '
if (-not $busy) {
    Start-Process $python -ArgumentList "src\guppy\cli\launch.py api" -WorkingDirectory $root -WindowStyle Minimized
    Start-Sleep -Seconds 5
}

# Open the web UI in Edge app mode
Start-Process $edge "--app=http://127.0.0.1:8081/index.html --window-size=1280,900"
