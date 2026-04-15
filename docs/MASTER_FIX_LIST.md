# Master Fix List

Last updated: 2026-04-14

This file is the execution ledger for the clean-framework migration. It turns the
12 review themes into a concrete sequence of bounded phases with verification at
each stop.

## Phase Ledger

- Phase 1: runtime artifact hygiene, legacy inventory, migration docs
- Phase 2: repair-token lifecycle correctness and routing classification fixes
- Phase 3: CI/test alignment and temp/test artifact cleanup
- Phase 4: legacy-surface quarantine and wrapper slimming
- Phase 5: modular refactor of oversized runtime modules in bounded slices
- Phase 6: follow-up cleanup, doc sync, and final verification

## 12-Item Master Fix List

- 1. Repo hygiene and secret safety
  Remove tracked runtime state, generated reports, live logs, tokens, and PID files from source control.
- 2. Repair token flow
  Ensure launcher/API token resync always prefers the active runtime token and has regression coverage.
- 3. CI and test alignment
  Make automated checks reflect the actual default test suite and local developer workflow.
- 4. Giant-module decomposition
  Split oversized files into domain modules with thin orchestration entrypoints.
- 5. Exception handling cleanup
  Replace broad fallbacks with structured error paths and explicit degradation rules.
- 6. Routing quality
  Correct simple/complex/teaching classification edge cases and keep the policy test-backed.
- 7. UI interaction polish
  Make launcher behaviors consistent, explicit, and status-rich across all surfaces.
- 8. Builder and off-hours hardening
  Keep write paths approval-first, safe-root constrained, and observable.
- 9. Documentation and encoding cleanup
  Remove drift, fix mojibake, and keep one clear source of truth per concern.
- 10. Architecture consistency
  Finish the move toward canonical `src/guppy/*` modules and keep wrappers thin.
- 11. Database and runtime reliability
  Enforce shared DB access policy and harden corrupted/truncated runtime-file handling.
- 12. Product scope discipline
  Keep launcher-first daily-assistant flow primary until stability and parity are complete.

## Phase 1 Acceptance Criteria

- Generated runtime artifacts are ignored and no longer tracked.
- Hygiene guard catches the most common runtime-file regressions.
- Legacy surfaces are inventoried with explicit quarantine targets.
- This ledger and the quarantine protocol are in place.

## Verification Contract

- After each phase, run the narrowest relevant checks first.
- If a phase changes runtime/auth/routing behavior, add or update tests in the same phase.
- Do not start the next bounded phase until current-phase verification is recorded.
