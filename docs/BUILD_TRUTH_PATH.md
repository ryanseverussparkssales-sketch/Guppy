# Build Truth Path

Last updated: 2026-04-17

## Canonical Command Surface

Use `tools/dev_workflow.py` as the single local and CI entrypoint:

```powershell
python tools/dev_workflow.py dev-check --guard-scope delta
python tools/dev_workflow.py test-fast
python tools/dev_workflow.py test-default
python tools/dev_workflow.py test-smoke
python tools/dev_workflow.py release-check
```

This command family is the only supported truth path for build verification. If a check matters in CI or release prep, it should be reachable through one of these subcommands instead of being documented only as a manual one-off.

## Command Meanings

1. `dev-check`
   Runs build guardrails and audits: line cap, architecture boundaries, runtime artifact hygiene, wrapper integrity, core surface integrity, doc ownership, and tool schema audit.
2. `test-fast`
   Runs the unit-focused fast path with workspace-local pytest temp/cache directories.
3. `test-default`
   Runs the default `tests/unit` + `tests/integration` suite.
4. `test-smoke`
   Runs runtime smoke, launcher interaction smoke, and security hardening smoke coverage.
5. `release-check`
   Runs release-oriented validation, including guardrails, default tests, smoke tests, and `tools/validate_build_checks.py`.

## When To Use Which Command

1. `dev-check`
   Before or during implementation when you want fast guardrails without paying for the whole test stack.
2. `test-fast`
   When changing seam contracts, launcher application services, or other unit-testable behavior and you want the quickest trustworthy feedback loop.
3. `test-default`
   Before handing work off or merging when the change may touch unit and integration behavior beyond one seam.
4. `test-smoke`
   When launcher/runtime behavior changed in a way that needs product-surface confidence.
5. `release-check`
   When preparing servicing, packaging, or a reviewer handoff bundle.

## Shared Workflow Definitions

Operational launcher workflows are now defined in `src/guppy/launcher_application/workflows.py`.

1. App Mgmt should consume workflow specs from that catalog instead of embedding command recipes in view code.
2. Build/release docs should refer to the canonical workflow/build commands instead of inventing parallel names.
3. Windows verify/update/package/release dry-run flows and the daily workflow loops should stay reviewable in one place.

## Workspace-Safe Temp and Cache Policy

`tools/dev_workflow.py` pins temp and cache state inside `.tmp/dev-workflow/`:

1. temp dirs: `.tmp/dev-workflow/tmp`
2. Python bytecode cache: `.tmp/dev-workflow/pycache`
3. general caches: `.tmp/dev-workflow/cache`
4. pytest cache: `.tmp/dev-workflow/pytest-cache`
5. pytest base temp: `.tmp/dev-workflow/pytest-basetemp/`

`pytest.ini` also defaults the pytest cache directory to `.tmp/pytest-cache` so direct `pytest` runs stay inside the workspace.

This matters locally because the current Windows environment has shown machine-global temp permission failures. The canonical workflow entrypoint keeps scratch state inside the repo so focused test runs are more repeatable.

## CI Lane Mapping

`.github/workflows/quality-gates.yml` maps the canonical commands into three CI lanes:

1. `guardrails`
   `python tools/dev_workflow.py dev-check --guard-scope <delta|baseline>`
2. `default-tests`
   `python tools/dev_workflow.py test-default`
3. `product-smoke`
   `python tools/dev_workflow.py test-smoke`

`release-check` is the canonical release-lane bundle for local validation, release prep, and future release workflow reuse.

The CI lanes intentionally stop short of running `release-check` on every PR. PR validation should prove guardrails, default tests, and smoke coverage; release packaging and handoff artifacts remain a separate gate.

## Release Outputs

`release-check` writes:

1. a machine-readable JSON receipt
2. a short human-readable summary

Default output location:

1. `.tmp/dev-workflow/reports/release-check-receipt.json`
2. `.tmp/dev-workflow/reports/release-check-summary.txt`
