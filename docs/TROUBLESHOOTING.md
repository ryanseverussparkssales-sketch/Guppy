# Troubleshooting

## Cloudflare tunnel: "origin cert not found"
- Run login once:
  - `powershell -ExecutionPolicy Bypass -File bin/cloudflare_terminal.ps1 -Action login`
- Complete browser authorization flow.
- Re-check:
  - `powershell -ExecutionPolicy Bypass -File bin/cloudflare_terminal.ps1 -Action status`

## API auth returns 500
- Confirm latest code is running (restart API process).
- Ensure dependencies are installed from `requirements.txt`.
- In strict mode (default), API startup fails if `GUPPY_JWT_SECRET` or `TURNSTILE_SECRET` is missing.
- For local-only development bypass, set `GUPPY_DEV_MODE=1` and restart the API.

## Voice endpoint returns 400 "Could not transcribe audio"
- This is expected for silence or very low-quality input.
- Test with clear spoken audio WAV.
- Ensure Whisper dependencies load correctly on your machine.

## Ollama connection issues
- Verify Ollama service is running:
  - `ollama serve`
- Verify model availability:
  - `ollama list`

## UI feels buggy / slow
- Review runtime performance logs:
  - `python runtime/review_agent_performance.py`
- Check `runtime/agent_performance.jsonl` for fallback and error spikes.
