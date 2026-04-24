param(
    [string]$DesktopRoot = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$applicationsDir = Join-Path $DesktopRoot "Applications"
$batchPath = Join-Path $applicationsDir "Guppy Launcher.bat"
$shortcutPath = Join-Path $DesktopRoot "Guppy Launcher.lnk"
$iconPath = Join-Path $repoRoot "assets\desktop\guppy_launcher_icon.ico"
$packagedOnedir = Join-Path $repoRoot "dist\Guppy\Guppy.exe"
$packagedOnefile = Join-Path $repoRoot "dist\Guppy.exe"

New-Item -ItemType Directory -Path $applicationsDir -Force | Out-Null

$batchBody = @"
@echo off
setlocal
TITLE Guppy Launcher

set "REPO_ROOT=$repoRoot"
set "REPO_LAUNCHER=%REPO_ROOT%\bin\Guppy.bat"
set "PACKAGED_ONEDIR=%REPO_ROOT%\dist\Guppy\Guppy.exe"
set "PACKAGED_ONEFILE=%REPO_ROOT%\dist\Guppy.exe"

cd /d "%REPO_ROOT%"

if exist "%PACKAGED_ONEDIR%" (
  start "" /D "%REPO_ROOT%\dist\Guppy" "%PACKAGED_ONEDIR%"
  exit /b 0
)

if exist "%PACKAGED_ONEFILE%" (
  start "" /D "%REPO_ROOT%\dist" "%PACKAGED_ONEFILE%"
  exit /b 0
)

if exist "%REPO_LAUNCHER%" (
  call "%REPO_LAUNCHER%"
  exit /b %ERRORLEVEL%
)

echo Guppy launcher helper not found.
echo Expected:
echo   %REPO_LAUNCHER%
pause
exit /b 1
"@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($batchPath, ($batchBody -replace "`r?`n", "`r`n"), $utf8NoBom)

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcutTarget = $batchPath
$shortcutWorkingDirectory = $repoRoot
if (Test-Path -LiteralPath $packagedOnedir) {
    $shortcutTarget = $packagedOnedir
    $shortcutWorkingDirectory = Split-Path -Parent $packagedOnedir
} elseif (Test-Path -LiteralPath $packagedOnefile) {
    $shortcutTarget = $packagedOnefile
    $shortcutWorkingDirectory = Split-Path -Parent $packagedOnefile
}
$shortcut.TargetPath = $shortcutTarget
$shortcut.WorkingDirectory = $shortcutWorkingDirectory
$shortcut.Description = "Launch Guppy"
if (Test-Path -LiteralPath $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()

Write-Output "Desktop batch: $batchPath"
Write-Output "Desktop shortcut: $shortcutPath"
Write-Output "Shortcut target: $shortcutTarget"
Write-Output "Repo root: $repoRoot"
