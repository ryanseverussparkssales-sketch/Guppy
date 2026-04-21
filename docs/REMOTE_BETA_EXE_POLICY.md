# Remote Beta EXE Policy

Date: April 12, 2026

This policy defines how to ship Guppy to remote beta testers with limited codebase and runtime access.

## Beta Package Shape

1. Ship one-folder executable build only.
2. Include only required runtime assets and policy files.
3. Exclude source repository, tests, and internal tooling by default.

## Access Boundaries

1. Default to read-mostly tools for beta profile.
2. Gate all write-side actions behind explicit user confirmation.
3. Block dangerous/system-level tools unless explicitly approved for a tester cohort.
4. Require signed-in session with scoped token for remote features.

## Auth and Scope

1. Use per-tester credentials, never shared global keys.
2. Support rapid revoke and rotate.
3. Enforce rate limits per tester profile.
4. Record scoped claims in audit logs for each remote action.

## Logging and Audit

1. Keep local action log stream for support diagnostics.
2. Mirror critical action events to telemetry store when network is available.
3. Capture tool name, decision path, confirmation state, and outcome.

## Data Handling

1. Store only minimum required local data for runtime operation.
2. Keep credentials encrypted at rest.
3. Backup policy for beta users uses snapshot manifests and excludes secrets by default.

## Beta Exit Criteria

1. Restricted tool policy test passes.
2. Auth scope and revocation test passes.
3. No unrestricted code execution path is reachable from default beta UI flow.
4. Pilot gate result is GO or LIMITED_GO during beta packaging window.

## Rollout Stages

1. Stage A: internal dogfood EXE with beta policy enabled.
2. Stage B: 3-5 trusted remote testers with support monitoring.
3. Stage C: broader beta cohort after two stable weekly cycles.
