@echo off
REM start_llm_backends.bat — Launch all three llama.cpp inference servers
REM Pepe 8B (port 8082), Qwen3 35B uncensored (port 8083), Gemma 4 E4B (port 8080)
REM Each server runs in its own window. Close the windows to stop them.

TITLE Guppy — Starting LLM Backends

echo Starting Pepe 8B (port 8082)...
start "LLM: Pepe 8B" cmd /k "C:\llama-cpp\launch-pepe.bat"

echo Starting Qwen3 35B Uncensored (port 8083)...
start "LLM: Qwen3 Uncensored" cmd /k "C:\llama-cpp\launch-qwen3.bat"

echo Starting Gemma 4 E4B (port 8080)...
start "LLM: Gemma 4" cmd /k "C:\llama-cpp\launch-gemma.bat"

echo.
echo All three backends launching in separate windows.
echo Pepe loads fastest (~30s). Wait for each to print "llama server listening" before chatting.
echo.
echo To verify:
echo   curl http://127.0.0.1:8082/v1/models
echo   curl http://127.0.0.1:8083/v1/models
echo   curl http://127.0.0.1:8080/v1/models
echo.
pause
