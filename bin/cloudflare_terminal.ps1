param(
    [ValidateSet("status", "install", "login", "create", "dns", "run", "service", "all")]
    [string]$Action = "status",
    [string]$TunnelName = "guppy",
    [string]$Hostname = "guppy.yourdomain.com",
    [string]$LocalUrl = "http://localhost:8081"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "[Cloudflare] $msg" -ForegroundColor Cyan
}

function Get-CloudflaredPath {
    # Prefer the bundled binary in bin/ so the script works without a system install
    $scriptDir = Split-Path -Parent $PSScriptRoot
    $bundled = Join-Path $scriptDir "bin\cloudflared.exe"
    if (Test-Path $bundled) { return $bundled }

    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "C:\Program Files\cloudflared\cloudflared.exe",
        "C:\Program Files (x86)\cloudflared\cloudflared.exe",
        "$env:LOCALAPPDATA\Programs\cloudflared\cloudflared.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Require-Cloudflared {
    if (-not (Get-CloudflaredPath)) {
        throw "cloudflared not found. Run: winget install Cloudflare.cloudflared"
    }
}

function Show-Status {
    Write-Step "Checking cloudflared installation"
    $cf = Get-CloudflaredPath
    if ($cf) {
        & $cf version
        Write-Step "Known tunnels"
        & $cf tunnel list
    }
    else {
        Write-Warning "cloudflared is not installed"
    }
}

function Install-Cloudflared {
    Write-Step "Installing cloudflared via winget"
    winget install Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements
}

function Login-Cloudflare {
    Require-Cloudflared
    $cf = Get-CloudflaredPath
    Write-Step "Opening Cloudflare login flow"
    & $cf tunnel login
}

function Create-Tunnel {
    Require-Cloudflared
    $cf = Get-CloudflaredPath
    Write-Step "Creating tunnel '$TunnelName'"
    & $cf tunnel create $TunnelName
}

function Configure-DNS {
    Require-Cloudflared
    $cf = Get-CloudflaredPath
    Write-Step "Routing hostname '$Hostname' to tunnel '$TunnelName'"
    & $cf tunnel route dns $TunnelName $Hostname
}

function Run-Tunnel {
    Require-Cloudflared
    $cf = Get-CloudflaredPath
    Write-Step "Running tunnel '$TunnelName' to $LocalUrl"
    & $cf tunnel run --url $LocalUrl $TunnelName
}

function Install-Service {
    Require-Cloudflared
    $cf = Get-CloudflaredPath
    Write-Step "Installing cloudflared as Windows service"
    & $cf service install
}

switch ($Action) {
    "status" { Show-Status }
    "install" { Install-Cloudflared }
    "login" { Login-Cloudflare }
    "create" { Create-Tunnel }
    "dns" { Configure-DNS }
    "run" { Run-Tunnel }
    "service" { Install-Service }
    "all" {
        Install-Cloudflared
        Login-Cloudflare
        Create-Tunnel
        Configure-DNS
        Run-Tunnel
    }
}
