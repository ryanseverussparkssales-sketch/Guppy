# Current Core Validation And Quarantine Audit

Date: April 22, 2026

Purpose:
- isolate the currently working core
- record what is proven healthy versus what is duplicate, historical, or purge-candidate
- provide a safe quarantine-first basis for any later delete pass

## Executive Summary

The repo is not yet ready for a destructive purge pass.

What is true right now:
- Core guardrails are green.
- The default unit/integration suite is green.
- The full `release-check` is currently failing on the launcher smoke lane.
- The largest obvious non-live mass is under `splits/` and `dist/`.
- `docs/archive/`, `docs/generated/`, and `documentation/` cannot be purged wholesale because they are still referenced by active docs and tooling.

## Validation Results

Commands run:
- `.\.venv\Scripts\python.exe tools/dev_workflow.py release-check`

Observed results:
- Guardrails delta: pass
- Guardrails baseline: pass
- Release comment-debt guard: pass
- Default unit+integration suite: `625 passed, 2 skipped`
- Product smoke suite inside `release-check`: fail

Primary failing lane:
- `tests/smoke/test_launcher_interactions_smoke.py`

Current failing checks from the smoke suite:
- disabled placeholder tooltip expectations in topbar button copy
- first-run banner status mapping
- `_shell_model_loadout_summary` launcher method exposure
- `_refresh_instance_views` dummy compatibility expectations
- sidebar badge structure expectation
- user test evidence pack output expectation

Interpretation:
- The repo has a healthy validated core, but the launcher integration seam is still mid-transition.
- Purging now would make it harder to distinguish real dead weight from active refactor fallout.

## Proven Working Core

The following areas currently have the strongest evidence and should be treated as hard keep:

- Root launch entrypoints:
  - `guppy_launcher.py`
  - `guppy_api.py`
  - `guppy_hub.py`
- Live Python app/runtime code:
  - `src/`
  - `compat_shims/`
  - `ui/`
  - `utils/`
- Validation and tooling:
  - `tests/`
  - `tools/`
  - `pytest.ini`
  - `pyproject.toml`
- Canonical docs:
  - `docs/PROJECT_BRIEF.md`
  - `README.md`
  - `docs/README.md`
  - canonical keep set from `docs/generated/DOC_RETENTION_CLASSIFICATION_20260420.md`
- Runtime/config/assets:
  - `config/`
  - `assets/`
  - `runtime/`
- Backup web surface:
  - `web/`

## Directory Weight Snapshot

Approximate file counts:
- `src`: `439`
- `compat_shims`: `161`
- `ui`: `14`
- `tests`: `448`
- `tools`: `60`
- `docs`: `66`
- `documentation`: `4`
- `config`: `15`
- `assets`: `2`
- `runtime`: `367`
- `web`: `16`
- `splits`: `3409`
- `stitch_azure_reef_assistant (1)`: `10`
- `build`: `17`
- `dist`: `16762`
- `guppy_core`: `16`
- `api`: `18`

## Quarantine-First Candidates

These are the safest first quarantine targets because they are either duplicate trees, generated packaging output, or obvious reference bundles:

1. `splits/`
   - no live markdown references found in the active tree scan
   - extremely large duplicate/historical surface
   - best first quarantine target

2. `dist/`
   - packaged output, very large
   - not source of truth
   - should be treated as disposable build artifact unless you intentionally want to preserve a release image

3. `build/`
   - build artifact surface
   - safe quarantine candidate after confirming nothing local depends on it

4. `stitch_azure_reef_assistant (1)/`
   - only directly referenced by the new Builder/Stitch mapping artifact
   - should be quarantined, not deleted, if we want to preserve the original design source bundle

## Not Purgeable Yet

These should not be purged in the first pass:

- `docs/archive/`
  - still referenced by active docs
- `docs/generated/`
  - still referenced by active docs, release posture, and runtime follow-up artifacts
- `documentation/`
  - still referenced by active docs
- `runtime/`
  - active runtime state and evidence paths live here
- `tests/`
  - needed to validate the isolation effort

## Safe Execution Order

1. Freeze destructive changes until launcher smoke failures are resolved.
2. Quarantine only duplicate/output/reference surfaces first:
   - `splits/`
   - `dist/`
   - `build/`
   - optionally `stitch_azure_reef_assistant (1)/`
3. Re-run `release-check`.
4. Only after a green `release-check`, evaluate tracked doc removal candidates from the retention contract.

## Recommendation

Do not purge tracked source or docs yet.

The safest immediate cleanup move is:
- quarantine `splits/`
- quarantine `dist/`
- quarantine `build/`
- keep all live source, tests, canonical docs, and runtime paths intact

Then:
- fix the current launcher smoke regressions
- re-run `release-check`
- perform a second, narrower purge pass against proven-unreferenced tracked docs
