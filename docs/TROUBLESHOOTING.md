# Troubleshooting

## Cloudflare tunnel: "origin cert not found"

- Run login once:
  - `powershell -ExecutionPolicy Bypass -File bin/cloudflare_terminal.ps1 -Action login`
- Complete browser authorization flow.
- Re-check:
  - `powershell -ExecutionPolicy Bypass -File bin/cloudflare_terminal.ps1 -Action status`

## API auth returns 500

- Confirm latest code is running (restart API process).
- Ensure base dependencies are installed from `requirements.txt`.
- In strict mode (default), API startup fails if `GUPPY_JWT_SECRET` or `TURNSTILE_SECRET` is missing.
- For local-only development bypass, set `GUPPY_DEV_MODE=1` and restart the API.

## Optional wake-word or Chroma features are missing

- Install optional extras: `python -m pip install -r requirements-optional.txt`
- `openwakeword` is only needed for the wake-word fast path.
- `chromadb` is only needed when `GUPPY_SEMANTIC_BACKEND=chroma`.

## Voice endpoint returns 400 "Could not transcribe audio"

- This is expected for silence or very low-quality input.
- Test with clear spoken audio WAV.
- Ensure Whisper dependencies load correctly on your machine.

## Voice endpoint returns 413 or rejects the upload before transcription

- The API now rejects oversized voice uploads before they hit transcription.
- Reduce the file size or trim long recordings before retrying.
- Adjust `GUPPY_VOICE_UPLOAD_MAX_BYTES` only when the machine has enough memory headroom for larger audio files.

## Persona, route, or voice changes do not appear in the launcher

- Re-open Settings, Models, or Voices and confirm the change was saved, not just previewed.
- Check the backing files under `runtime/`:
  - `persona_config.json`
  - `provider_registry.json`
  - `voice_bindings.json`
- Run the focused builder sweep:
  - `python -m pytest tests/unit/test_personalization_resolution.py tests/unit/test_models_routes.py tests/unit/test_voices_view_validation.py -q`
- Use App Mgmt `WORKFLOW LOOPS` to load the acceptance or midday checks without leaving the launcher.

## Ollama connection issues

- Verify Ollama service is running:
  - `ollama serve`
- Verify model availability:
  - `ollama list`

## UI feels buggy / slow

- Review runtime performance logs:
  - `python tools/review_agent_performance.py`
- Check `runtime/agent_performance.jsonl` for fallback and error spikes.

## Agents show OFFLINE / DAEMON: STOPPED at launch

- The launcher auto-starts the API and hub on open. If they still don't appear:
  1. Check `runtime/hub.pid` — if it exists but the process is gone, delete it and reopen the launcher.
  2. Check that psutil is installed: `python -m pip install psutil` (required for hub liveness check).
  3. Look at launcher logs: `runtime/launcher_events.jsonl` for startup failure messages.

## Recovery tools failing (WinError 10061 / connection refused)

- This means the API server is not running on port 8081.
- The launcher should auto-start it, but if it failed: `python src/guppy/cli/launch.py api` in a terminal.
- Alternatively, use the launcher's direct recovery path — warmup/audit/snapshot now work without the API.

## /repair returns 403 Forbidden

- The /repair endpoint requires an `X-Repair-Token` header matching the API process token.
- Token source order is now:
  - OS credential store (`keyring`) key `repair_token`
  - fallback file `runtime/repair_token.txt` when keyring is unavailable
- This token is generated fresh each time the API process starts.
- The launcher reads token automatically when calling recovery actions.

## PowerShell windows flashing at startup or during operation

- This was fixed in the April 13 build. All subprocess calls now use CREATE_NO_WINDOW on Windows.
- If still happening, the call is likely from a third-party tool or script, not Guppy itself.
