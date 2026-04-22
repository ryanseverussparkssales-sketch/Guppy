# Guppy Local Model Diagnostic Script - Simple Version
# Run this on your Windows machine to diagnose GPU and Ollama setup
# Usage: powershell -ExecutionPolicy Bypass -File diagnose_local_models.ps1

param()

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$outputFile = ".\guppy_diagnostic_$timestamp.txt"

Write-Host "Guppy Local Model Diagnostic" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Output will be saved to: $outputFile" -ForegroundColor Yellow
Write-Host ""

# Create output file
"=== Guppy Local Model Diagnostic ===" | Out-File -FilePath $outputFile
"Timestamp: $timestamp" | Out-File -FilePath $outputFile -Append
"Computer: $env:COMPUTERNAME" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 1. Check Installed Models
# ============================================================================
Write-Host "1. Checking installed Ollama models..." -ForegroundColor Green

"--- 1. INSTALLED OLLAMA MODELS ---" | Out-File -FilePath $outputFile -Append
"Command: ollama list" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

$models = $null
$models = @(ollama list 2>$null)
if ($models -and $models.Count -gt 0) {
    $models | Out-File -FilePath $outputFile -Append
    Write-Host "✓ Models found:" -ForegroundColor Green
    foreach ($model in $models) {
        Write-Host "  $model"
    }
} else {
    "ERROR: No models found or Ollama not running" | Out-File -FilePath $outputFile -Append
    Write-Host "✗ Error: Ollama not found or not running" -ForegroundColor Red
    Write-Host "  Make sure Ollama is installed and running" -ForegroundColor Yellow
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 2. Check AMD GPU Availability
# ============================================================================
Write-Host "2. Checking AMD GPU availability..." -ForegroundColor Green

"--- 2. AMD GPU DETECTION ---" | Out-File -FilePath $outputFile -Append
"Command: Get-CimInstance CIM_VideoController" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

$gpu = $null
$gpu = @(Get-CimInstance CIM_VideoController -ErrorAction SilentlyContinue | Select-Object Name, Description, AdapterMemory)

if ($gpu -and $gpu.Count -gt 0) {
    $gpu | Format-Table -AutoSize | Out-File -FilePath $outputFile -Append

    $amdGpu = $gpu | Where-Object { $_.Name -like "*AMD*" -or $_.Name -like "*Radeon*" }
    if ($amdGpu) {
        Write-Host "✓ AMD GPU detected:" -ForegroundColor Green
        foreach ($device in $amdGpu) {
            $vram = [math]::Round($device.AdapterMemory / 1GB, 2)
            Write-Host "  $($device.Name) - $vram GB VRAM"
        }
    } else {
        Write-Host "⚠ No AMD GPU detected" -ForegroundColor Yellow
        Write-Host "  Available GPUs:" -ForegroundColor Yellow
        foreach ($device in $gpu) {
            Write-Host "  $($device.Name)"
        }
    }
} else {
    "ERROR: Could not detect GPU" | Out-File -FilePath $outputFile -Append
    Write-Host "✗ Error detecting GPU" -ForegroundColor Red
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 3. Check ROCm Installation
# ============================================================================
Write-Host "3. Checking ROCm installation..." -ForegroundColor Green

"--- 3. ROCm STATUS ---" | Out-File -FilePath $outputFile -Append
"Command: rocm-smi --showid" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

$rocm = $null
$rocm = @(rocm-smi --showid 2>$null)

if ($rocm -and $rocm.Count -gt 0) {
    $rocm | Out-File -FilePath $outputFile -Append
    Write-Host "✓ ROCm is installed" -ForegroundColor Green
    foreach ($line in $rocm) {
        Write-Host "  $line"
    }
} else {
    "ROCm not found in PATH" | Out-File -FilePath $outputFile -Append
    Write-Host "✗ ROCm not installed or not in PATH" -ForegroundColor Red
    Write-Host "  Download from: https://rocmdocs.amd.com/en/latest/deploy/windows/quick_start.html" -ForegroundColor Yellow
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 4. Performance Benchmark - guppy-fast
# ============================================================================
Write-Host "4. Running performance benchmark (guppy-fast)..." -ForegroundColor Green
Write-Host "   This will take 10-30 seconds..." -ForegroundColor Yellow

"--- 4. PERFORMANCE BENCHMARK (guppy-fast) ---" | Out-File -FilePath $outputFile -Append
"Model: guppy-fast" | Out-File -FilePath $outputFile -Append
"Query: 'What is the capital of France?'" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

$startTime = Get-Date
$response = @(ollama run guppy-fast "What is the capital of France?" 2>$null)
$elapsed = (Get-Date) - $startTime

if ($response) {
    "Response Time: $($elapsed.TotalSeconds) seconds" | Out-File -FilePath $outputFile -Append
    "Response: $($response -join ' ')" | Out-File -FilePath $outputFile -Append

    Write-Host "✓ Benchmark complete" -ForegroundColor Green
    Write-Host "  Response time: $($elapsed.TotalSeconds) seconds" -ForegroundColor Cyan

    if ($elapsed.TotalSeconds -lt 2) {
        Write-Host "  → Likely using GPU (fast)" -ForegroundColor Green
    } elseif ($elapsed.TotalSeconds -lt 5) {
        Write-Host "  → Mixed GPU/CPU or partial GPU utilization" -ForegroundColor Yellow
    } else {
        Write-Host "  → Likely CPU-only (slow)" -ForegroundColor Red
    }
} else {
    "ERROR: Benchmark failed or model not found" | Out-File -FilePath $outputFile -Append
    Write-Host "✗ Benchmark failed" -ForegroundColor Red
    Write-Host "  Make sure Ollama is running and guppy-fast model exists" -ForegroundColor Yellow
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 5. Performance Benchmark - guppy (full model)
# ============================================================================
Write-Host "5. Running performance benchmark (guppy full 32B)..." -ForegroundColor Green
Write-Host "   This will take 30-120 seconds..." -ForegroundColor Yellow

"--- 5. PERFORMANCE BENCHMARK (FULL MODEL) ---" | Out-File -FilePath $outputFile -Append
"Model: guppy" | Out-File -FilePath $outputFile -Append
"Query: 'Write a short poem about AI'" | Out-File -FilePath $outputFile -Append
"" | Out-File -FilePath $outputFile -Append

$startTime = Get-Date
$response = @(ollama run guppy "Write a short poem about AI" 2>$null)
$elapsed = (Get-Date) - $startTime

if ($response) {
    "Response Time: $($elapsed.TotalSeconds) seconds" | Out-File -FilePath $outputFile -Append
    "Response: $($response -join ' ')" | Out-File -FilePath $outputFile -Append

    Write-Host "✓ Benchmark complete" -ForegroundColor Green
    Write-Host "  Response time: $($elapsed.TotalSeconds) seconds" -ForegroundColor Cyan

    if ($elapsed.TotalSeconds -lt 5) {
        Write-Host "  → Excellent (likely using GPU)" -ForegroundColor Green
    } elseif ($elapsed.TotalSeconds -lt 15) {
        Write-Host "  → Good (GPU + partial CPU)" -ForegroundColor Yellow
    } elseif ($elapsed.TotalSeconds -lt 60) {
        Write-Host "  → Slow (CPU-heavy or partial GPU)" -ForegroundColor Yellow
    } else {
        Write-Host "  → Very slow (CPU-only)" -ForegroundColor Red
    }
} else {
    "ERROR: Benchmark failed or model not installed" | Out-File -FilePath $outputFile -Append
    Write-Host "⚠ Benchmark skipped or failed" -ForegroundColor Yellow
    Write-Host "  (guppy model may not be installed)" -ForegroundColor Yellow
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 6. Ollama Logs
# ============================================================================
Write-Host "6. Collecting Ollama logs..." -ForegroundColor Green

"--- 6. OLLAMA LOGS (Last 100 lines) ---" | Out-File -FilePath $outputFile -Append

$logPath = "$env:LOCALAPPDATA\Ollama\logs"
if (Test-Path $logPath) {
    $logs = @(Get-ChildItem $logPath -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    if ($logs -and $logs.Count -gt 0) {
        $logContent = @(Get-Content $logs[0].FullName -Tail 100 -ErrorAction SilentlyContinue)
        if ($logContent) {
            $logContent | Out-File -FilePath $outputFile -Append
            Write-Host "✓ Logs collected from: $($logs[0].Name)" -ForegroundColor Green
        }
    }
} else {
    "WARNING: Log directory not found at $logPath" | Out-File -FilePath $outputFile -Append
    Write-Host "⚠ Logs not found at default location" -ForegroundColor Yellow
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# 7. System Information
# ============================================================================
Write-Host "7. Collecting system information..." -ForegroundColor Green

"--- 7. SYSTEM INFORMATION ---" | Out-File -FilePath $outputFile -Append

$os = Get-CimInstance CIM_OperatingSystem -ErrorAction SilentlyContinue
$cpu = Get-CimInstance CIM_Processor -ErrorAction SilentlyContinue
$mem = Get-CimInstance CIM_PhysicalMemory -ErrorAction SilentlyContinue | Measure-Object -Property Capacity -Sum

if ($os) {
    "OS: $($os.Caption)" | Out-File -FilePath $outputFile -Append
    "Version: $($os.Version)" | Out-File -FilePath $outputFile -Append
}

if ($cpu) {
    "CPU: $($cpu[0].Name)" | Out-File -FilePath $outputFile -Append
    "Cores: $($cpu[0].NumberOfCores) / Logical: $($cpu[0].NumberOfLogicalProcessors)" | Out-File -FilePath $outputFile -Append
}

if ($mem) {
    $totalGB = [math]::Round($mem.Sum / 1GB, 2)
    "RAM: $totalGB GB" | Out-File -FilePath $outputFile -Append
}

"" | Out-File -FilePath $outputFile -Append

# ============================================================================
# Final Summary
# ============================================================================
Write-Host ""
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Diagnostic complete!" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Output saved to:" -ForegroundColor Cyan
Write-Host "  $outputFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "1. Open the file and review the results" -ForegroundColor Green
Write-Host "2. Share the file contents with Claude for analysis" -ForegroundColor Green
Write-Host ""
Write-Host "To view the results:" -ForegroundColor Green
Write-Host "  Get-Content $outputFile" -ForegroundColor Cyan
Write-Host "  OR" -ForegroundColor Cyan
Write-Host "  notepad $outputFile" -ForegroundColor Cyan

# Open file
Write-Host ""
notepad.exe $outputFile
