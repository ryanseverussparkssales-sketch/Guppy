# Goals Sheet

Last updated: April 14, 2026

## Product Goals

1. Be a dependable Windows daily assistant, not just a demo assistant.
2. Make persona, model, and voice customization first-class and easy.
3. Keep local-first reliability while allowing cloud quality upgrades.
4. Preserve low-friction voice behavior with immediate interruption handling.
5. Maintain safe, observable, and recoverable operation.

## Measurable Targets

### User Experience

1. Time-to-first-use on an existing machine: under 10 minutes.
2. Time-to-first-response for simple requests: under 3 seconds median.
3. Voice stop-on-user-input success rate: 100 percent in smoke checks.

### Reliability

1. Pilot gate script returns GO for release candidates.
2. No mandatory gate failures in two consecutive daily runs.
3. Recovery actions resolve common faults without manual file edits.

### Builder Completion

1. Persona builder supports global and per-model profiles with preview.
2. Model assignment supports fallback chains and effective route preview.
3. Voice builder supports import, assignment, preview, and fallback policy.

## Current Build Coverage (Handled Now)

1. Launcher foundation and tab surfaces are in place.
2. Local model fleet and runtime verifiers are operational.
3. Provider and logging verifiers are available.
4. Persona Builder v1, model routing visibility, and voice assignment/import/preview are live in the launcher.
5. Recovery, health status, and off-hours builder queue flows are present.

## Gaps To Close

1. Builder polish: stronger guardrails, empty states, and broader real-device validation.
2. In-app daily workflow loop and evidence capture for Morning, Workday, and Close.
3. App-level onboarding and installer/update flow.
4. Broader hardware fallback behavior policy.

## This Week Priorities

1. Productize workflow loops in launcher App Mgmt and runbook docs.
2. Harden pilot-gate coverage so builder regressions are part of the release signal.
3. Expand builder and voice validation across more machines and failure cases.
4. Keep daily pilot gate runs and track failures to closure.

## Go Decision Rule

1. GO when all mandatory pilot gates pass and builder v1 flows are usable end-to-end.
2. LIMITED GO only when mandatory gates pass but optional provider breadth is reduced.
3. NO GO when any mandatory gate fails.
