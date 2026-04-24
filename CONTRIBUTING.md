# Contributing

## Development Setup
1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
   - `pip install -r requirements-dev.txt`
   - `pip install -r requirements-optional.txt` only when working on optional wake-word or Chroma paths

## Common Run Commands
- Launcher: `python src/guppy/cli/launch.py launcher`
- GuppyPrime: `python src/guppy/cli/launch.py guppyprime`
- Hub: `python src/guppy/cli/launch.py hub`
- API server: `python src/guppy/cli/launch.py api`
- CLI surface: `python guppy_agent.py`

Historical specialist surfaces are quarantined and should not be used as active entrypoints. Use the launcher, hub, API, or CLI agent flows above.

## Project Boundaries
- `Guppy` and `Guppy-pi` are separate development tracks and must not be edited together in one workflow.
- Do not include `Guppy-pi/` file edits in Guppy commits, guardrail runs, or release validation.
- `python tools/dev_workflow.py dev-check` now runs `tools/check_project_isolation.py` first and fails if `Guppy-pi` is dirty.
- Emergency local bypass only: set `GUPPY_ALLOW_CROSS_PROJECT_DIRTY=1` for one-off local investigation runs.

## Tests and Quality
- Run tests: `python -m pytest`
- Compile sanity check:
   - `python -m py_compile guppy_launcher.py guppy_hub.py guppy_api.py src/guppy/cli/launch.py`
- Manual smoke checks:
   - `python tests/smoke/smoke_api.py`
   - `python tests/integration/test_ptt.py`

## Pull Request Checklist
- Keep changes scoped and avoid unrelated refactors.
- Update docs when adding env vars, endpoints, launch flows, or moving canonical module paths.
- Verify no new warnings/errors in VS Code Problems panel.
- Add or update smoke tests for endpoint behavior changes.
