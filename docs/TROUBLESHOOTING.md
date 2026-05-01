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

## A connector action is blocked and the reason is unclear

- Open Agent Tools for the active workspace and read the tool card details.
- Blocked actions now explain whether the stop came from:
  - workspace not bound to that connector
  - connector action policy
  - account or provider mismatch
  - missing host auth
  - endpoint scope filtering
  - coarse workspace policy
- Open Workspaces and review both editors for that workspace:
  - governance editor:
    - `auth mode`
    - `tool allow` / `tool block`
    - `endpoint allow` / `endpoint block`
    - operator note
  - connector bindings editor:
    - `enabled`
    - `account_id`
    - `provider`
    - `action allow` / `action block`
    - `endpoint allow` / `endpoint block`
    - operator note
- Open App Mgmt `CONNECTOR INVENTORY + AUTH` when the fix belongs to machine auth instead of workspace policy:
  - use `VERIFY` to confirm readiness
  - use `CONNECT` / `RECONNECT` for OAuth- or file-backed connectors
  - use `SAVE SECRET` / `CLEAR SECRET` for API-key or provider-secret connectors
- App Mgmt `WINDOWS INSTALL / UPDATE / DIAGNOSTICS` remains the right place to verify which local runtime is active, where Guppy stores data, and which repair path to try next.

## Connector verify/connect/reconnect/disconnect does not do what I expect

- Open App Mgmt `CONNECTOR INVENTORY + AUTH`.
- Choose the connector first, then set provider/account only when that connector exposes them.
- If the connector uses secrets:
  - select the secret field from the dropdown
  - enter the value
  - use `SAVE SECRET` to persist it through the machine-level connector flow
- If `VERIFY` still reports missing auth:
  - confirm the expected env var or keyring entry exists
  - for Gmail/Calendar/Spotify, confirm the expected token/cache or credential files are present on this machine
  - for CRM/VoIP, confirm the selected provider is actually the one configured
- If App Mgmt shows the connector ready but the tool is still blocked, the remaining issue is usually the active workspace binding or its connector endpoint/action policy in Workspaces.

## Need to know what is installed, which runtime is active, or where Guppy stores data

- Open App Mgmt and read the `WINDOWS INSTALL / UPDATE / DIAGNOSTICS` section.
- It now shows:
  - installed runtime/tooling signals (`.venv`, Ollama CLI, Lemonade CLI, supervisor script, packager)
  - configured and live local runtime backend
  - runtime/config/settings data paths
  - repair-token posture and the supervisor relaunch path
  - latest diagnostics artifact and launcher log path
- It also gives one-click actions for `VERIFY`, `UPDATE`, `PACKAGE`, `SUPERVISED API`, `RESTART`, and `REPAIR`:
  - `VERIFY` queues the runtime verification commands in the embedded terminal
  - `UPDATE` queues dependency refresh plus postflight validation
  - `PACKAGE` queues the supported packaging entry point plus beta package-policy verification
  - `SUPERVISED API` launches `bin/launch_api_supervised.bat` from the launcher and checks reachability
  - `RESTART` uses the guarded daemon restart path
  - `REPAIR` runs the warmup plus audit flow
- The panel now also shows:
  - the last servicing action and stable ref when available
  - what changed after the action completed
  - the next recommended fix path, docs hint, and command entry point

## Ollama connection issues

- Verify Ollama service is running:
  - `ollama serve`
- Verify model availability:
  - `ollama list`

## UI feels buggy / slow

- Review runtime performance logs:
  - `python tools/review_agent_performance.py`
- Check `runtime/agent_performance.jsonl` for fallback and error spikes.
- If `/api/status` is slow, reduce backend probe overhead:
  - `GUPPY_BACKEND_PROBE_TTL_SECONDS=5` (default) or higher to cache backend liveness
  - `GUPPY_MODEL_LIST_TTL_SECONDS=20` (default) or higher to cache model lists

## Agents show OFFLINE / DAEMON: STOPPED at launch

- The launcher auto-starts the API and hub on open. If they still don't appear:
  1. Check `runtime/hub.pid` — if it exists but the process is gone, delete it and reopen the launcher.
  2. Check that psutil is installed: `python -m pip install psutil` (required for hub liveness check).
  3. Look at launcher logs: `runtime/launcher_events.jsonl` for startup failure messages.

## Recovery tools failing (WinError 10061 / connection refused)

- This means the API server is not running on port 8081.
- The launcher should auto-start it. App Mgmt `SUPERVISED API` is now the first productized retry path.
- If you still want the manual fallback: `python src/guppy/cli/launch.py api` in a terminal.
- Alternatively, use the launcher's direct recovery path — warmup/audit/snapshot now work without the API.

## Packaging or install follow-up is unclear

- Open App Mgmt `WINDOWS INSTALL / UPDATE / DIAGNOSTICS`.
- Use the launcher-first order:
  - `VERIFY`
  - `UPDATE` if dependencies/runtime posture changed
  - `PACKAGE` when you need a desktop build
- If you are reviewing a release candidate or beta gate, use `RELEASE DRY RUN` after `PACKAGE` so the receipt and summary stay current.
- Read the final servicing summary:
  - `Ref:` gives the stable operator-facing package/update reference
  - `What changed:` calls out the detected environment or artifact delta
  - `Operator Guidance:` points at the right fix target, doc, and command
- For release dry runs, read the matching handoff files in this order:
  - `runtime/beta_release_dry_run_report.json`
  - `runtime/windows_release_receipt.json`
  - `runtime/windows_release_summary.md`
- The summary is the human-readable handoff. If it says `Next Review Step`, follow the `Review`, `Doc`, and `Cmd` lines to hand off or package the current bundle.
- If it says `Fix-First`, follow the `Fix in`, `Doc`, and `Cmd` lines before rerunning the dry run.
- When you hand the bundle to another reviewer, pass the same three files in that order and call out the `Review Order` section so they know the report was read before the receipt and summary.
- Use the deeper docs when you need non-default flows:
  - `docs/PACKAGING.md` for build variants and release checklist work
  - `docs/SUPERVISION_WINDOWS.md` for Task Scheduler or NSSM ownership

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
