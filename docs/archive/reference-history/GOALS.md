# Goals Sheet

Last updated: April 16, 2026

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

## Current Execution Priorities (Apr 16 - May 29, 2026)

1. April 16 - April 24: close release-lane hardening, align handoff artifacts, and keep servicing evidence/operator summaries stable.
2. April 27 - May 08: move Workspace Framing into the active lane with clearer workspace language, recurring-context cues, and collaboration-fit direction.
3. May 11 - May 22: land Home/chat-first polish, first-run guidance, and calmer starter flows without pushing operator-heavy context back onto Home.
4. May 25 - May 29: run a mid-M2 review and decide whether Route + Voice Trust starts on June 1, 2026 or waits behind remaining servicing/release risk.

## Go Decision Rule

1. GO when all mandatory pilot gates pass and builder v1 flows are usable end-to-end.
2. LIMITED GO only when mandatory gates pass but optional provider breadth is reduced.
3. NO GO when any mandatory gate fails.
