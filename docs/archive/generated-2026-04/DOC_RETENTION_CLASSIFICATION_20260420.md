# Doc Retention Classification (2026-04-20)

This report records a live classification pass for tracked docs under `docs/` and `documentation/`.
The objective is to support quarantine and purge decisions while preserving direct repo processes.

## Keep: Canonical Active Docs

- `docs/PROJECT_BRIEF.md`
- `docs/GUPPY_PRODUCT_NORTH_STAR.md`
- `docs/PRODUCT_FEATURE_FILTER.md`
- `docs/API.md`
- `docs/TROUBLESHOOTING.md`
- `docs/VOICE.md`
- `docs/PACKAGING.md`
- `docs/LIVE_ARCHITECTURE.md`
- `docs/BUILD_TRUTH_PATH.md`
- `docs/LEGACY_SURFACES.md`
- `docs/DAILY_WORKFLOW.md`
- `docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`
- `docs/README.md`
- `documentation/README.md`
- `documentation/ARCHITECTURE.md`
- `documentation/SECURITY.md`
- `documentation/TRUTH_AUDIT.md`

## Keep: Historical/Archive (non-active source of truth)

- `docs/archive/**`
- `docs/archive/root-history/ROADMAP_2026-04-17.md`
- `docs/archive/planning-history/**`

## Keep: Generated Evidence currently referenced by active docs/tools

- `docs/generated/RUNTIME_VALIDATION_MATRIX.md`
- `docs/generated/VOICE_VALIDATION_MATRIX.md`
- `docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md`
- `docs/generated/PRE_LAUNCH_READINESS_20260420.md`
- `docs/generated/TRANCHE_53_GOALS_UI_AUDIT_20260420.md`
- `docs/generated/TRANCHE_53_INTEGRATED_AUDIT_20260420.md`
- `docs/generated/TRANCHE_53_SECURITY_AUDIT_20260420.md`
- `docs/generated/TRANCHE_53_STITCH_DELTA_20260420.md`
- `docs/generated/TRANCHE_54_MODULE_BREAKUP_AND_STITCH_EXECUTION_CARDS_20260420.md`
- `docs/generated/TRANCHE_55_DESKTOP_ASSISTANT_EXECUTION_CARDS_20260421.md`

## Quarantine Candidates (review before purge)

These appear non-canonical or superseded and should be moved to a quarantine bucket first, then purged after reference scan + release checks:

- `docs/ARCHITECTURE_IMPLEMENTATION_STATUS.md`
- `docs/AUTHORIZATION_AND_FEATURE_FLAG_DEEP_DIVE.md`
- `docs/HUB_CONSOLIDATION_MASTER_PLAN.md`
- `docs/IMPLEMENTATION_READY_INDEX.md`
- `docs/PHASE_0_KICKOFF_ALL_HANDS.md`
- `docs/SEQUENTIAL_TRANCHE_EXECUTION_PLAN.md`
- `docs/FEATURE_FLAG_STRATEGY.md`
- `docs/CLEANUP_BEFORE_DEMO_CHECKLIST.md`
- `docs/LAUNCHER_UI_RESET_2026-04-17.md`
- `docs/PROJECT_BOB_INTEGRATION_CONTRACT.md`
- `docs/SECURITY_GATE.md`
- `docs/GOALS.md`
- `docs/MEMPALACE_EVALUATION.md`
- `docs/SEED_VAULT_STORAGE.md`
- `docs/generated/RELEASE_GATE_CHECKLIST.md`
- `docs/generated/TRANCHE_CLOSEOUT_2026-04-19.md`
- `documentation/BASE_FUNCTIONALITY_RECOVERY.md`

## Hard Keep (currently referenced and therefore not purge-eligible)

Referenced by active docs and tools:

- `docs/archive/root-history/ROADMAP_2026-04-17.md`
- `docs/REMOTE_BETA_EXE_POLICY.md`
- `docs/generated/VOICE_VALIDATION_MATRIX.md`
- `docs/generated/RUNTIME_VALIDATION_MATRIX.md`
- `docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md`

## Next Execution Steps

1. Produce a reference graph (`README`, `PROJECT_BRIEF`, `tools/*`) for all quarantine candidates.
2. Move unreferenced candidates into `docs/archive/reference-history/` with a dated closeout note.
3. Re-run `python tools/dev_workflow.py dev-check --guard-scope delta` and smoke bundle.
4. Remove quarantine candidates only after one green release-check cycle.

## Addendum (2026-04-21)

1. `docs/generated/TRANCHE_55_DESKTOP_ASSISTANT_EXECUTION_CARDS_20260421.md` is now an active generated planning artifact because `docs/PROJECT_BRIEF.md` references it directly for the end-state desktop assistant execution deck.
