# Create Desktop Shortcuts for Guppy Launchers
# Run this once to create all shortcuts on Desktop

param(
    [switch]$Force = $false
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")

Write-Host "=== Creating Guppy Desktop Shortcuts ===" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot" -ForegroundColor Gray
Write-Host "Desktop: $desktopPath" -ForegroundColor Gray
Write-Host ""

# Function to create shortcut
function Create-Shortcut {
    param(
        [string]$Name,
        [string]$Target,
        [string]$Arguments,
        [string]$IconPath,
        [string]$Description,
        [string]$WorkingDirectory
    )

    $shortcutPath = Join-Path $desktopPath "$Name.lnk"
    
    if ((Test-Path $shortcutPath) -and -not $Force) {
        Write-Host "  ⏭️  $Name (already exists, use -Force to overwrite)" -ForegroundColor Gray
        return
    }

    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $shortcut = $WshShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $Target
        if ($Arguments) { $shortcut.Arguments = $Arguments }
        if ($IconPath) { $shortcut.IconLocation = $IconPath }
        if ($Description) { $shortcut.Description = $Description }
        if ($WorkingDirectory) { $shortcut.WorkingDirectory = $WorkingDirectory }
        $shortcut.Save()
        
        Write-Host "  ✅ $Name" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ $Name - Error: $_" -ForegroundColor Red
    }
}

# Get paths
$batDir = Join-Path $repoRoot "bin"
$apiScript = Join-Path $batDir "launch_api_dev.bat"
$webScript = Join-Path $batDir "launch_web_ui.bat"
$desktopScript = Join-Path $batDir "launch_desktop_ui.bat"
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source

# Check if scripts exist
if (-not (Test-Path $apiScript)) {
    Write-Host "❌ Error: $apiScript not found" -ForegroundColor Red
    exit 1
}

Write-Host "Creating shortcuts..." -ForegroundColor Yellow
Write-Host ""

# Create shortcuts
Create-Shortcut `
    -Name "Guppy - API Server" `
    -Target "cmd.exe" `
    -Arguments "/k `"$apiScript`"" `
    -IconPath "$repoRoot\assets\icon_api.ico" `
    -Description "Start Guppy API server (localhost:8000)" `
    -WorkingDirectory $repoRoot

Create-Shortcut `
    -Name "Guppy - Web UI" `
    -Target "cmd.exe" `
    -Arguments "/k `"$webScript`"" `
    -IconPath "$repoRoot\assets\icon_web.ico" `
    -Description "Start Guppy Web UI (localhost:3000)" `
    -WorkingDirectory $repoRoot

Create-Shortcut `
    -Name "Guppy - Desktop Launcher" `
    -Target "cmd.exe" `
    -Arguments "/k `"$desktopScript`"" `
    -IconPath "$repoRoot\assets\icon_desktop.ico" `
    -Description "Start Guppy Desktop Launcher UI" `
    -WorkingDirectory $repoRoot

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Desktop shortcuts created:" -ForegroundColor Cyan
Write-Host "  • Guppy - API Server       (localhost:8000)" -ForegroundColor White
Write-Host "  • Guppy - Web UI           (localhost:3000)" -ForegroundColor White
Write-Host "  • Guppy - Desktop Launcher (native app)" -ForegroundColor White
Write-Host ""
Write-Host "Before using, make sure Ollama is running:" -ForegroundColor Yellow
Write-Host "  ollama serve" -ForegroundColor Gray
Write-Host ""
Write-Host "Click any shortcut on Desktop to start!" -ForegroundColor Cyan
