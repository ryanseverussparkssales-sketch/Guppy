# Cleanup Before Demo

Last reviewed: April 16, 2026

This checklist splits repo cleanup into three buckets:

- `Delete now`: generated or disposable artifacts we can remove immediately without changing the supported product path.
- `Quarantine after demo`: tracked or compatibility material that should stay available until the demo build, installer pass, and release handoff are stable.
- `Keep for ship`: current product code, live docs, and evidence needed to explain or validate the shipped demo.

## Delete Now

- [x] `build/`
- [x] `dist/`
- [x] `.mypy_cache/`
- [x] `.pytest_cache/`
- [x] root `__pycache__/`
- [x] `src/__pycache__/`
- [x] `src/guppy/__pycache__/`
- [x] `tests/__pycache__/`
- [x] `tests/unit/__pycache__/`
- [x] `tests/smoke/__pycache__/`
- [x] `tests/integration/__pycache__/`
- [x] `tools/__pycache__/`
- [x] `ui/components/__pycache__/`
- [x] `ui/launcher/__pycache__/`
- [x] `compat_shims/legacy_surfaces/__pycache__/`

Notes:

- These are generated outputs, caches, or build products.
- Removing them should force the next demo build to be a fresh one.

## Quarantine After Demo

- [x] `docs/archive/planning-history/m2/`
- [x] `compat_shims/legacy_surfaces/`
- [x] non-UI compatibility shim aliases under `compat_shims/`
- [x] tracked repo-local `chroma_db/`
- [x] `src/guppy/apps/guppy_surface_app.py`
- [x] `vendor/lemonade/`
- [x] `vendor/mempalace/`
- [x] `web/`
- [x] `tests/runtime/`
- [x] `runtime/llama_cpp_smoke/`
- [x] `runtime/runtime_compare/`
- [x] `runtime/local_memory/benchmark_runs/`
- [x] `runtime/daily_reports/`
- [ ] `docs/MASTER_FIX_LIST.md`
- [ ] `docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`
- [x] `docs/MEMPALACE_EVALUATION.md`
- [ ] `docs/LEGACY_QUARANTINE_PROTOCOL.md` after it is refreshed or replaced
- [ ] `docs/archive/` only after release-dry-run references stop pointing into it

Prerequisites before quarantining this bucket:

1. Complete one fresh installer-backed demo pass.
2. Run the launcher release dry-run and keep the handoff artifacts green.
3. Remove the last legacy launch hooks and prove no supported entrypoint still touches `compat_shims/legacy_surfaces/`.
4. Decide whether benchmark comparison folders stay in-repo or move to an external evidence archive.
5. Refresh stale cleanup docs so they match the live tree.

## Keep For Ship

- `src/`
- `ui/`
- `guppy_core/`
- `utils/`
- `tools/`
- `config/`
- `instructions/`
- `documentation/`
- `docs/PROJECT_BRIEF.md`
- `docs/API.md`
- `docs/PACKAGING.md`
- `docs/TROUBLESHOOTING.md`
- `docs/VOICE.md`
- `docs/CONFIG_SCHEMAS.md`
- `README.md`
- `ROADMAP.md` compatibility stub
- `docs/archive/root-history/ROADMAP_2026-04-17.md`
- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `pytest.ini`
- root compatibility wrappers such as `guppy_launcher.py`, `guppy_api.py`, and `guppy_hub.py`
- `runtime/local_llm_benchmarks/`
- `runtime/windows_release_receipt.json` when present
- `runtime/windows_release_summary.md` when present
- `runtime/connector_state.json`
- `runtime/windows_ops_state.json` if used by the launcher on this machine

Why this bucket stays:

- It contains the shipped product, the docs a demo user or operator still needs, or the evidence that supports the local-model and release decisions already made.

## Execution Log

- April 16, 2026: checklist created.
- April 16, 2026: immediate delete lane executed for build outputs and cache folders.
- April 16, 2026: runtime evidence quarantined under `runtime/quarantine/2026-04-16_pre_demo_runtime_quarantine/`.
- April 17, 2026: removed unreferenced non-UI compatibility shims and the tracked repo-local `chroma_db/` now that durable storage lives under user data.
- April 17, 2026: removed vendored Lemonade and MemPalace trees, the deprecated repo-local web UI, and checked-in `tests/runtime` reports after switching Guppy to external integration contracts plus `runtime/stress_reports/`.
