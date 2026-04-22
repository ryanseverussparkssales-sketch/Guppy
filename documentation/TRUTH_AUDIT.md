# Documentation Truth Audit

Audit date: 2026-04-17

This file records what was verified against live code and where legacy docs are
outdated or ambiguous.

## Verified True (against code)

1. Launcher-first architecture is active.
2. Thin wrapper model for launcher and hub is active.
3. `/repair` is token-guarded.
4. Supervisor-oriented operational pattern exists and is supported.
5. Launcher has direct-recovery fallback when API is unreachable.
6. Default dependency install is slimmer than before.
   - Dev-only packages now live in `requirements-dev.txt`.
   - Optional `openwakeword` and `chromadb` extras now live in `requirements-optional.txt`.
7. Canonical CLI launch no longer exposes `merlin` or `council` as supported surfaces.
   - `src/guppy/cli/launch.py` now supports only `guppy`, `launcher`, `guppyprime`, `hub`, and `api`.

## Drift / Needs Correction in Legacy Docs

1. Repair token storage wording in legacy docs is incomplete.
   - Some files describe only `runtime/repair_token.txt`.
   - Current code now prefers OS credential store with file fallback.

2. Entrypoint ownership wording in legacy docs can be stale.
   - Canonical launcher implementation now lives in `src/guppy/apps/launcher_app.py`.
   - Root `guppy_launcher.py` is compatibility wrapper.

3. Database connection guidance was inconsistent across docs.
   - Canonical policy is now centralized in `utils/db_utils.py`.

4. Voice docs include historical examples and may overstate current default paths.
   - Keep as reference, but verify behavior against `src/guppy/voice/voice.py` for production decisions.

5. Root-module references are widely stale outside canonical docs.
   - Core implementations now live under `src/guppy/*`.
   - Root launch shims are now limited to `guppy_launcher.py`, `guppy_hub.py`, and `guppy_api.py`.
- Historical compatibility-only desktop surfaces now live under `compat_shims/legacy_surfaces/`.

6. Test-path references drifted after suite reorganization.
   - Default pytest targets are now `tests/unit/` and `tests/integration/`.
   - Smoke and stress scripts live under `tests/smoke/`.

7. Review-tool paths drifted after runtime-script cleanup.
   - Performance review helpers now live in `tools/`, not `runtime/`.

## Consolidation Result

Canonical docs are now:

- Instructions: `instructions/README.md`, `instructions/OPERATIONS.md`, `instructions/DEVELOPMENT.md`
- Technical documentation: `documentation/README.md`, `documentation/ARCHITECTURE.md`, `documentation/SECURITY.md`, `documentation/TRUTH_AUDIT.md`
- Operational references: `docs/API.md`, `docs/TROUBLESHOOTING.md`, `docs/VOICE.md`, `docs/PACKAGING.md`
- Active status and roadmap reference: `docs/PROJECT_BRIEF.md`
- Historical roadmap and handoff archive: `docs/archive/root-history/ROADMAP_2026-04-17.md`

Legacy docs remain present for historical context and should be treated as
secondary unless migrated.
