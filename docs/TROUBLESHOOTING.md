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

## Agents show OFFLINE / DAEMON: STOPPED at launch
- The launcher auto-starts guppy_api.py and guppy_hub.py on open. If they still don't appear:
  1. Check `runtime/hub.pid` — if it exists but the process is gone, delete it and reopen the launcher.
  2. Check that psutil is installed: `python -m pip install psutil` (required for hub liveness check).
  3. Look at launcher logs: `runtime/launcher_events.jsonl` for startup failure messages.

## Recovery tools failing (WinError 10061 / connection refused)
- This means guppy_api.py is not running on port 8081.
- The launcher should auto-start it, but if it failed: `python guppy_api.py` in a terminal.
- Alternatively, use the launcher's direct recovery path — warmup/audit/snapshot now work without the API.

## /repair returns 403 Forbidden
- The /repair endpoint requires an `X-Repair-Token` header matching the API process token.
- Token source order is now:
  - OS credential store (`keyring`) key `repair_token`
  - fallback file `runtime/repair_token.txt` when keyring is unavailable
- This token is generated fresh each time `guppy_api.py` starts.
- The launcher reads token automatically when calling recovery actions.

## PowerShell windows flashing at startup or during operation
- This was fixed in the April 13 build. All subprocess calls now use CREATE_NO_WINDOW on Windows.
- If still happening, the call is likely from a third-party tool or script, not Guppy itself.
