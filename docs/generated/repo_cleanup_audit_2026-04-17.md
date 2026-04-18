# Repo Cleanup Audit

Date: 2026-04-17

## Scope

- code review and structural scan
- architecture and wrapper guard verification
- security regression pass
- legacy/dead-file reference scan

## Findings

1. Repo-supported launch paths still depend on root wrappers (`guppy_launcher.py`, `guppy_hub.py`, `guppy_api.py`), so those remain active.
2. Non-UI compatibility shim aliases under `compat_shims/` had no live code imports in `src/`, `ui/`, `tests/`, `tools/`, `docs/`, or `documentation/`.
3. The tracked repo-local `chroma_db/` directory was stale after storage moved to the Guppy user-data root.
4. Repo docs still described repo-local Chroma storage and fallback non-UI shims as active, which no longer matched code.
5. Local root files `entities.json` and `mempalace.yaml` were left in place because they may belong to the parallel Open WebUI / MemPalace setup and are not owned by the supported Guppy path.

## Actions

- remove unreferenced non-UI compatibility shim files under `compat_shims/`
- remove tracked repo-local `chroma_db/`
- quarantine repo-root legacy Guppy database files out of the root folder
- update cleanup, storage, security, and architecture docs to match the live tree
- add ignore rules for sidecar/local artifact files that should not be treated as source

## Verification

- `python tools/check_architecture_boundaries.py`
- `python tools/check_runtime_artifact_hygiene.py`
- `python tools/check_wrapper_integrity.py`
- `python -m pytest tests/test_security_hardening.py tests/unit/test_security_hardening.py -q`
- `python tools/dev_workflow.py dev-check --guard-scope delta`

## Deferred

- `vendor/lemonade/`, `vendor/mempalace/`, `web/`, and `tests/runtime/` remain because active docs, scripts, or smoke expectations still reference them.
- `entities.json` and `mempalace.yaml` remain because they may be owned by the temporary local Open WebUI / MemPalace stack rather than Guppy itself.
