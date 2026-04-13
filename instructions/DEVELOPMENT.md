# Development Instructions

Last verified: 2026-04-13

## 1) Environment

1. Use Python 3.12 virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Key dependency for current security model:
   - `keyring` (OS-backed secret storage)

## 2) Entrypoint Rules

1. Keep wrappers thin:
   - `guppy_launcher.py`
   - `guppy_hub.py`
2. Place real app logic under `src/guppy/apps/` and shared modules under `src/guppy/` or `ui/launcher/`.

## 3) Architecture Rules

1. Run boundary checks before merging:
   - `python tools/check_architecture_boundaries.py`
2. Keep changed `src/guppy/` modules under line-cap policy:
   - `python tools/check_new_module_line_cap.py`
3. Preserve wrapper integrity:
   - `python tools/check_wrapper_integrity.py`

## 4) Security Rules

1. Do not add new plaintext secret files when OS keyring is available.
2. Reuse `utils/secret_store.py` for secret retrieval/persistence.
3. Enforce request correlation for async UI worker responses.
4. Keep `/repair` guarded by token dependency.

## 5) DB Rules

1. Do not call `sqlite3.connect(...)` directly in product paths unless explicitly justified.
2. Use `utils/db_utils.py:open_db(...)` for consistent durability and lock behavior.
3. Keep schema setup close to module ownership, but connection policy centralized.

## 6) Test Expectations

Minimum merge gate for critical changes:

- `python -m pytest tests/test_runtime_smoke.py tests/test_launcher_interactions_smoke.py tests/test_security_hardening.py -v`

When touching API auth/repair/DB paths, add regression coverage in `tests/test_security_hardening.py`.
