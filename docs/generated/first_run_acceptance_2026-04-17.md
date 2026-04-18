# First-Run Acceptance - 2026-04-17

## Scope

- Desktop launch from `Desktop/Applications/Guppy Launcher.bat`
- Launcher bootstrap for `guppy_launcher.py`, `guppy_api.py`, and `guppy_hub.py`
- Home, Workspaces, Agent Tools, and App Mgmt launcher smoke coverage
- First-run startup quality, visible layout blockers, and tray/tool interaction readiness

## Acceptance Result

- `PASS` for desktop launch reliability and launcher smoke coverage
- `PASS` for hidden background bootstrap on Windows
- `PASS` for Agent Tools scroll access after the wheel/scrollbar fix
- `PASS` for workspace switch control sync, warm-start workspace fallback, and first-run discoverability

## Visible Defects Found

1. Desktop launch previously surfaced helper consoles for launcher bootstrap and API logs.
2. The launcher accepted stale `runtime/hub.pid` state too easily, which could block clean relaunches.
3. Agent Tools could trap the user in the catalog view because scroll affordances were weak.
4. Startup readiness used an auth-protected `/status` probe during bootstrap, which created noisy `401` requests and made startup look less stable than it was.
5. The startup warning budget was tuned far below the real launcher shell, so normal launches could present as `STARTUP WARN`.
6. Home updated workspace copy without updating the visible mode/persona controls after workspace changes.
7. Workspace create/delete actions failed too early during API warmup instead of falling back to launcher-local workspace state.
8. Top navigation buttons for `TOOLS` / `APP MGMT` were not discoverable because the nav buttons were built but not shown in the layout.
9. App Mgmt hid `CONNECTED SERVICES` behind the generic detail toggle, which made first-run connector setup harder to find.

## Fixes Applied

- Background launcher, hub, and API startup now stay on `pythonw` and log to runtime files instead of opening black console windows.
- Hub PID validation now clears stale or misidentified `hub.pid` state before deciding the hub is already alive.
- Agent Tools now exposes a persistent vertical scrollbar and forwards wheel scrolling across the catalog content.
- Launcher bootstrap now probes `http://127.0.0.1:8081/` instead of the auth-protected `/status` endpoint for readiness.
- The default startup warning budget now matches the real shell better at `3000ms`.
- Home now applies workspace mode/persona directly into the visible controls when the active workspace changes.
- Workspace create/delete now fall back to local `config/instances.json` and `runtime/instance_state.json` when the API is still warming.
- Top navigation now exposes visible `HOME`, `WORKSPACES`, `TOOLS`, and `APP MGMT` tabs, and App Mgmt keeps `CONNECTED SERVICES` visible on first render.
- `bin/Guppy.bat` now routes through `src/guppy/cli/launch.py launcher`, keeping the repo batch path aligned with the supported desktop launcher flow.

## Verification

- `python -m pytest tests/unit/test_launch_cli.py tests/unit/test_launcher_app_bootstrap.py -q`
- `python -m pytest tests/smoke/test_launcher_interactions_smoke.py -q`
- `python tools/dev_workflow.py dev-check --guard-scope delta`
- `python tools/dev_workflow.py release-check`
- Desktop relaunch verified from `Guppy Launcher.bat`
- API reachable after desktop launch on `127.0.0.1:8081`

## Remaining Notes

- The current launcher shell still has startup phases that are heavy enough to merit future optimization, but they no longer read as immediate launch failures.
- The next tranche should focus on interaction polish, layout cleanup, and consistency rather than first-run/startup correctness.
