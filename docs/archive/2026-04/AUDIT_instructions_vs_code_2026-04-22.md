# Audit: Canonical Brief vs. Code

**Date:** 2026-04-22
**Brief audited:** `instructions/README.md` → `instructions/OPERATIONS.md` (Last verified 2026-04-16) and `instructions/DEVELOPMENT.md` (Last verified 2026-04-14)
**Scope:** Full repo excluding `.venv/`, `.quarantine/`, `node_modules/`
**Depth:** Deep (existence + behavioral + reverse sweep)

---

## TL;DR

The canonical brief under `instructions/` is in good shape. Every path, script, flag, PRAGMA, env var, header, and route I spot-checked matches the code. The real issues are **outside** the canonical set: the root-level "Voice System" documentation describes a working subsystem whose supporting Python scripts are not in this repo, so its `.bat` launchers are broken. A couple of smaller drifts in the canonical brief are noted below.

---

## Findings requiring attention

### 1. Voice system at repo root is broken (HIGH)

`VOICE_SYSTEM_STATUS.md` and `VOICE_SETUP_GUIDE.md` (both at repo root) describe a voice subsystem as "FULLY OPERATIONAL" and list supporting Python modules. None of those modules exist in this repo.

Missing but referenced:

- `voice_listener.py` — launched by `start_voice_monitoring.bat` line 9
- `voice_integration.py` — launched by `start_hold_to_talk.bat` line 11
- `guppy_voice.py` — described as "already present" in `VOICE_SYSTEM_STATUS.md` line 194
- `test_voice_system.py`, `guppy_voice_demo.py`, `guppy_voice_bridge.py`, `check_voice_commands.py` — all listed as deliverables in the setup guide

Concrete consequence: double-clicking either `start_voice_monitoring.bat` or `start_hold_to_talk.bat` from this directory will fail — Python will not find the target scripts.

`VOICE_SETUP_GUIDE.md` line 201–204 also tells the user to `cd /d C:\Users\Ryan\` (not the Guppy folder) and run the scripts from there, so the voice system may actually live outside this repo and these files are just stranded copies. Either way, they are misleading here.

Additionally, `Open_Interpreter.bat` line 3 hard-codes `cd /d "C:\Users\Ryan\AI_Project"` — a directory outside this repo. The launcher is unrelated to Guppy and should probably be moved.

**Suggested action:** Either (a) delete the voice `.bat` files and the two VOICE `.md` files from this repo and move them under `C:\Users\Ryan\` where they belong, or (b) import the supporting `*.py` files into this repo so the launchers work. `Open_Interpreter.bat` should likely be moved/deleted for the same reason.

### 2. `compat_shims/legacy_surfaces/` is essentially empty (LOW)

`OPERATIONS.md` §2 line 21 says:

> Historical specialist material: `compat_shims/legacy_surfaces/` and `src/guppy/merlin/` (not active desktop entrypoints)

`src/guppy/merlin/` genuinely contains `catalog.py`, `core.py`, `specialist_support.py`. But `compat_shims/legacy_surfaces/` contains only a single file — `__init__.py` with a one-line docstring declaring the package "quarantined". There is no actual historical material under this directory.

**Suggested action:** Either delete the directory and remove the reference from `OPERATIONS.md`, or restore/point to the intended content.

### 3. `ui/launcher/` is a re-export shim, not where the UI code lives (LOW)

`OPERATIONS.md` §2 line 19 says:

> Primary UI: launcher (`ui/launcher/`)

`ui/launcher/__init__.py` is a 23-line compatibility shim (`__path__ = extend_path(...)`) that exposes the real modules from `compat_shims/launcher_ui/ui/launcher/`. The package resolves at runtime, so imports work — but a reader who `cd`s into `ui/launcher/` will find only `__init__.py`. This is fine if intentional (and the brief lives in instructions/, which is fine), but worth documenting so a new operator isn't confused about where to look.

**Suggested action:** Add a one-line note in `OPERATIONS.md` §2 clarifying that the real modules live under `compat_shims/launcher_ui/ui/launcher/`, or leave as-is if this is a deliberate cleanup in progress.

---

## Verified (everything the brief claims that does check out)

Paths and scripts — all present at the documented locations:

- `src/guppy/cli/launch.py`, `src/guppy/apps/launcher_app.py`, `src/guppy/apps/hub_app.py`
- `src/guppy/api/server.py`, `src/guppy/api/auth.py`
- `utils/secret_store.py`, `utils/db_utils.py`
- `guppy_launcher.py` (12 lines), `guppy_hub.py` (12 lines), `guppy_api.py` (12 lines) — all thin as brief requires
- `bin/launch_automation_test.bat`
- `config/instances.json` — contains `guppy-primary` (enabled) and `builder-collab` (enabled: false, i.e. optional), matches §2 exactly
- `requirements.txt`, `requirements-dev.txt`, `requirements-optional.txt`
- All 8 documented tool scripts: `tools/check_architecture_boundaries.py`, `check_wrapper_integrity.py`, `check_doc_ownership.py`, `check_new_module_line_cap.py`, `pilot_exit_check.py`, `verify_logging_health.py`, `verify_ollama_runtime.py`, `run_overnight_low_compute.py`
- All 10 documented test files: `tests/smoke/test_runtime_smoke.py`, `test_launcher_interactions_smoke.py`, `smoke_api.py`, `tests/unit/test_security_hardening.py`*, `test_instance_controls.py`, `test_offhours_builder.py`, `test_smart_dispatch.py`, `test_personalization_resolution.py`, `test_models_routes.py`*, `test_voices_view_validation.py`*

*\* Note: `test_security_hardening.py` lives at `tests/test_security_hardening.py`, not under `tests/unit/`. `test_models_routes.py` and `test_voices_view_validation.py` currently resolve via `compat_shims/launcher_ui/tests/` rather than `tests/unit/` — pytest picks them up on import, but the literal `tests/unit/test_...` path in the brief is imprecise. Pytest compiled caches under `tests/unit/__pycache__/` suggest these files previously lived there.*

Behavioral claims — verified against code:

- **PRAGMAs in `utils/db_utils.py:open_db()`** (§6) — all five applied at lines 89–93: `journal_mode=WAL`, `synchronous`, `busy_timeout`, `foreign_keys=ON`, `temp_store=MEMORY`.
- **JWT secret resolution in `src/guppy/api/auth.py`** (§5) — `jwt_secret` keyring key + `GUPPY_JWT_SECRET` env fallback, lines 36–41.
- **`GUPPY_DEV_MODE` env var** (§8) — read at `src/guppy/api/auth.py:36` and `:54`, logged on line 464.
- **`POST /repair` guarded by `X-Repair-Token` header** (§4, DEVELOPMENT §4) — header extracted at `src/guppy/api/_server_fragment_routes_core.py:270`; route declared at line 351 with `_require_repair_token` dependency at line 356.
- **`GET /repair-token/refresh`** (§4) — declared at `src/guppy/api/_server_fragment_routes_core.py:312` (and mirrored at `routes_ops.py:115`, `snapshot_misc_routes.py:64`).
- **CLI flags in §7** — all four flags resolve to the right `argparse` declarations: `pilot_exit_check.py:246` (`--allow-limited-go`), `verify_logging_health.py:53,55` (`--emit-probe`, `--require-fresh-core`), `verify_ollama_runtime.py:189` (`--skip-ping`).
- **Python 3.12 requirement** (DEVELOPMENT §1) — `pyproject.toml` declares `requires-python = ">=3.12"`.

---

## Observations (not errors, but worth noting)

**Multiple repair-token implementations.** `/repair` and `/repair-token/refresh` are declared in three files: `routes_ops.py`, `snapshot_misc_routes.py`, and `_server_fragment_routes_core.py`. If these are alternative mount points for different app topologies that's fine, but if one is dead code it's a good target for cleanup. The brief doesn't indicate which is authoritative.

**`api/` directory at repo root.** There is a top-level `api/` folder with a `requirements.txt` but no Python sources in it (at least none that the glob found). Not mentioned anywhere in `OPERATIONS.md`/`DEVELOPMENT.md`. Worth checking whether it's an abandoned surface.

**Other bin/\*.bat scripts not covered.** The brief mentions `bin/launch_automation_test.bat` but the `bin/` directory almost certainly has peers (e.g. launch shortcuts for hub/API/web-UI). The brief doesn't enumerate them — if any are first-class operator entrypoints, they belong in §1 or §2. If they're just IDE/dev conveniences, leaving them undocumented is fine.

---

## Meta-note on process

My first pass delegated verification to a sub-agent that hallucinated several "missing" findings (claimed 4 tool scripts and 10 test files did not exist; fabricated a quote from `docs/PROJECT_BRIEF.md`, a file that also doesn't exist). All of those "findings" were wrong and are excluded from this report. Everything above was re-verified against direct tool output. If any item still looks off, the best reproduction is the exact grep / glob at the line numbers cited.
