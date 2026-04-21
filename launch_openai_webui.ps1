param(
    [string]$ContainerName = "openai-webui",
    [string]$Image = "ghcr.io/open-webui/open-webui:main",
    [int]$HostPort = 3000,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[OpenAI WebUI] $Message"
}

Write-Step "Checking Docker availability..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install Docker Desktop first."
}

try {
    docker info | Out-Null
} catch {
    throw "Docker daemon is not running. Start Docker Desktop and run again."
}

$apiKey = $env:OPENAI_API_KEY
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host ""
    Write-Host "OPENAI_API_KEY is not set."
    Write-Host "Set it once with:"
    Write-Host '  [System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY","sk-...","User")'
    Write-Host ""
    exit 1
}

Write-Step "Pulling latest WebUI image ($Image)..."
docker pull $Image

$existingContainer = docker ps -a --filter "name=^/$ContainerName$" --format "{{.ID}}"
if ($existingContainer -and $Recreate) {
    Write-Step "Recreating existing container..."
    docker rm -f $ContainerName | Out-Null
    $existingContainer = $null
}

if (-not $existingContainer) {
    Write-Step "Creating container $ContainerName..."
    docker run -d `
        -p "${HostPort}:8080" `
        -e "OPENAI_API_KEY=$apiKey" `
        -e "OPENAI_API_BASE_URL=https://api.openai.com/v1" `
        -v "${ContainerName}-data:/app/backend/data" `
        --name $ContainerName `
        --restart unless-stopped `
        $Image | Out-Null
} else {
    $runningContainer = docker ps --filter "name=^/$ContainerName$" --format "{{.ID}}"
    if (-not $runningContainer) {
        Write-Step "Starting existing container..."
        docker start $ContainerName | Out-Null
    } else {
        Write-Step "Container already running."
    }
}

$url = "http://localhost:$HostPort"
Write-Step "Waiting for WebUI at $url ..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 1
}

$edge = Get-Command msedge.exe -ErrorAction SilentlyContinue
$chrome = Get-Command chrome.exe -ErrorAction SilentlyContinue

if ($edge) {
    Start-Process $edge.Source "--app=$url --new-window"
    Write-Step "Opened dedicated Edge app window."
} elseif ($chrome) {
    Start-Process $chrome.Source "--app=$url --new-window"
    Write-Step "Opened dedicated Chrome app window."
} else {
    Start-Process $url
    Write-Step "Opened in default browser."
}

Write-Step "Done."
