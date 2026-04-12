param(
    [string]$AccountId = $env:CLOUDFLARE_ACCOUNT_ID,
    [string]$ApiToken = $env:CLOUDFLARE_API_TOKEN,
    [string]$Domain = "",
    [string]$WidgetName = "Guppy Turnstile Widget",
    [ValidateSet("managed", "non-interactive", "invisible")]
    [string]$Mode = "managed",
    [switch]$SkipFileUpdates
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $repoRoot ".env"
$webJsPath = Join-Path $repoRoot "web/turnstile.js"

function Get-TunnelAccountTag {
    param(
        [string]$EnvFilePath
    )

    $tunnelId = Get-EnvFileValue -Path $EnvFilePath -Key "CLOUDFLARE_TUNNEL_ID"
    if ([string]::IsNullOrWhiteSpace($tunnelId)) {
        return ""
    }

    $credentialPath = Join-Path $HOME ".cloudflared\$tunnelId.json"
    if (-not (Test-Path $credentialPath)) {
        return ""
    }

    try {
        $credential = Get-Content $credentialPath -Raw | ConvertFrom-Json
        return ($credential.AccountTag | Out-String).Trim()
    }
    catch {
        return ""
    }
}

function Get-EnvFileValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$([Regex]::Escape($Key))\s*=\s*" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }

    return ($line -split "=", 2)[1].Trim()
}

function Set-EnvFileValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    if (-not (Test-Path $Path)) {
        throw "Missing .env file at $Path"
    }

    $lines = Get-Content $Path
    $pattern = "^\s*$([Regex]::Escape($Key))\s*="
    $replacement = "$Key=$Value"
    $updated = $false

    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = $replacement
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $lines += $replacement
    }

    Set-Content -Path $Path -Value $lines
}

if ([string]::IsNullOrWhiteSpace($Domain)) {
    $Domain = Get-EnvFileValue -Path $envPath -Key "CLOUDFLARE_HOSTNAME"
}

if ([string]::IsNullOrWhiteSpace($AccountId)) {
    $AccountId = Get-TunnelAccountTag -EnvFilePath $envPath
}

if ([string]::IsNullOrWhiteSpace($Domain) -or $Domain -like "*.yourdomain.com" -or $Domain -eq "yourdomain.com") {
    throw "A real domain is required. Pass -Domain 'guppy.yourdomain.com' or set CLOUDFLARE_HOSTNAME in .env"
}

if ([string]::IsNullOrWhiteSpace($AccountId)) {
    throw "CLOUDFLARE_ACCOUNT_ID is missing. Pass -AccountId, set env var, or configure CLOUDFLARE_TUNNEL_ID with a local cloudflared credential file."
}

if ([string]::IsNullOrWhiteSpace($ApiToken)) {
    throw "CLOUDFLARE_API_TOKEN is missing. Pass -ApiToken or set env var."
}

$uri = "https://api.cloudflare.com/client/v4/accounts/$AccountId/challenges/widgets"
$headers = @{
    Authorization = "Bearer $ApiToken"
}
$payload = @{
    domains = @($Domain)
    mode = $Mode
    name = $WidgetName
} | ConvertTo-Json -Depth 5

Write-Host "Creating Turnstile widget for domain: $Domain"
try {
    $response = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType "application/json" -Body $payload
}
catch {
    $statusCode = $null
    $responseBody = ""

    if ($_.Exception.Response) {
        try {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        catch {
            $statusCode = $null
        }

        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
        }
        catch {
            $responseBody = ""
        }
    }

    if ($statusCode -eq 401) {
        throw "Cloudflare rejected the API token with HTTP 401. Verify CLOUDFLARE_API_TOKEN has Account:Turnstile:Edit permission and is copied correctly."
    }

    if ($statusCode -eq 403) {
        throw "Cloudflare denied access with HTTP 403. Verify the account ID matches the token scope and that the token has Account:Turnstile:Edit permission."
    }

    if (-not [string]::IsNullOrWhiteSpace($responseBody)) {
        throw "Cloudflare API request failed with HTTP $statusCode. Response: $responseBody"
    }

    throw
}

if (-not $response.success) {
    $errors = ($response.errors | ConvertTo-Json -Compress)
    throw "Cloudflare API returned success=false. errors=$errors"
}

$result = $response.result
$siteKey = $result.sitekey
$secret = $result.secret
$widgetId = $result.widget_id

if ([string]::IsNullOrWhiteSpace($siteKey)) {
    throw "Widget created but sitekey missing in API response."
}

Write-Host "Turnstile widget created."
Write-Host "- Widget ID: $widgetId"
Write-Host "- Site key: $siteKey"

if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Warning "Secret was not returned by the create response. Retrieve/rotate secret in Cloudflare dashboard or API and set TURNSTILE_SECRET manually."
}

if (-not $SkipFileUpdates) {
    if (-not [string]::IsNullOrWhiteSpace($secret)) {
        Set-EnvFileValue -Path $envPath -Key "TURNSTILE_SECRET" -Value $secret
        Write-Host "Updated .env TURNSTILE_SECRET"
    }

    Set-EnvFileValue -Path $envPath -Key "TURNSTILE_SITE_KEY" -Value $siteKey
    Write-Host "Updated .env TURNSTILE_SITE_KEY"

    if (Test-Path $webJsPath) {
        $js = Get-Content $webJsPath -Raw
        $updatedJs = [Regex]::Replace(
            $js,
            "const TURNSTILE_SITE_KEY\s*=\s*'[^']*';",
            "const TURNSTILE_SITE_KEY = '$siteKey';"
        )

        if ($updatedJs -ne $js) {
            Set-Content -Path $webJsPath -Value $updatedJs
            Write-Host "Updated web/turnstile.js TURNSTILE_SITE_KEY"
        }
    }
}

Write-Host "Done."