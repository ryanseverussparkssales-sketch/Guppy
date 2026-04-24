$outputFile = "guppy_diagnostic.txt"

Write-Host "Running diagnostics..."
Write-Host ""

"=== Guppy Diagnostic Report ===" | Out-File $outputFile
"Generated: $(Get-Date)" | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 1. Ollama models
Write-Host "1. Checking Ollama models..."
"--- 1. INSTALLED MODELS ---" | Out-File $outputFile -Append
ollama list | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 2. GPU
Write-Host "2. Checking GPU..."
"--- 2. GPU INFO ---" | Out-File $outputFile -Append
Get-CimInstance CIM_VideoController | Select-Object Name, AdapterMemory | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 3. ROCm
Write-Host "3. Checking ROCm..."
"--- 3. ROCm STATUS ---" | Out-File $outputFile -Append
rocm-smi --showid | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 4. Test guppy-fast
Write-Host "4. Testing guppy-fast (will take 10-30 seconds)..."
"--- 4. GUPPY-FAST TEST ---" | Out-File $outputFile -Append
$start = Get-Date
ollama run guppy-fast "What is 2+2?" | Out-File $outputFile -Append
$time = (Get-Date) - $start
"Time: $($time.TotalSeconds) seconds" | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 5. Test guppy
Write-Host "5. Testing guppy full model (will take 30-120 seconds)..."
"--- 5. GUPPY FULL TEST ---" | Out-File $outputFile -Append
$start = Get-Date
ollama run guppy "Tell me about AI in one sentence" | Out-File $outputFile -Append
$time = (Get-Date) - $start
"Time: $($time.TotalSeconds) seconds" | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

# 6. System info
Write-Host "6. Getting system info..."
"--- 6. SYSTEM INFO ---" | Out-File $outputFile -Append
Get-CimInstance CIM_OperatingSystem | Select-Object Caption, Version | Out-File $outputFile -Append
Get-CimInstance CIM_Processor | Select-Object Name, NumberOfCores | Out-File $outputFile -Append
"" | Out-File $outputFile -Append

Write-Host ""
Write-Host "Done! Results saved to: $outputFile"
Write-Host ""
notepad $outputFile
