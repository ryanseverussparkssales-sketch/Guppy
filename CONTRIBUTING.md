# Contributing

## Development Setup
1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy environment template:
   - `copy .env.example .env` (Windows)

## Common Run Commands
- Guppy GUI: `python guppy_ui.py`
- Merlin UI: `python merlin_ui.py`
- Council UI: `python council_ui.py`
- API server: `python guppy_api.py`

## Tests and Quality
- Run tests: `python -m pytest`
- Compile sanity check:
  - `python -m py_compile guppy_ui.py merlin_ui.py guppy_api.py`

## Pull Request Checklist
- Keep changes scoped and avoid unrelated refactors.
- Update docs when adding env vars, endpoints, or launch scripts.
- Verify no new warnings/errors in VS Code Problems panel.
- Add or update smoke tests for endpoint behavior changes.
