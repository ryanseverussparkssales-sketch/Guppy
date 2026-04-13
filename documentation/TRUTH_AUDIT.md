# Documentation Truth Audit

Audit date: 2026-04-13

This file records what was verified against live code and where legacy docs are
outdated or ambiguous.

## Verified True (against code)

1. Launcher-first architecture is active.
2. Thin wrapper model for launcher and hub is active.
3. `/repair` is token-guarded.
4. Supervisor-oriented operational pattern exists and is supported.
5. Launcher has direct-recovery fallback when API is unreachable.

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
   - Keep as reference, but verify behavior against `guppy_voice.py` for production decisions.

## Consolidation Result

Canonical docs are now:

- Instructions: `instructions/README.md`, `instructions/OPERATIONS.md`, `instructions/DEVELOPMENT.md`
- Technical documentation: `documentation/README.md`, `documentation/ARCHITECTURE.md`, `documentation/SECURITY.md`, `documentation/TRUTH_AUDIT.md`

Legacy docs remain present for historical context and should be treated as
secondary unless migrated.
