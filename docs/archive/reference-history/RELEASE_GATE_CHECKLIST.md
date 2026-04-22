# Release Gate Checklist

Last updated: April 18, 2026

**Purpose:** Pre-release checklist to be copy-pasted into a PR description or release ticket. All gates must be checked before a build is promoted.

---

## Section A — Existing Acceptance Gates

Gate Owner: **Engineering lead**
Last verified: _____________

These four gates are defined in `docs/PROJECT_BRIEF.md` § "Current Acceptance Gates". Reference them here; do not duplicate their definitions.

- [ ] **Gate 1 — Build guardrails pass:** `python tools/dev_workflow.py dev-check --guard-scope baseline` exits clean (architecture boundaries, line-cap policy, wrapper integrity, runtime artifact hygiene, doc ownership).
- [ ] **Gate 2 — Default test suite passes:** `python tools/dev_workflow.py test-default` — all unit and integration tests green.
- [ ] **Gate 3 — Smoke suite passes:** `python tools/dev_workflow.py test-smoke` — launcher interaction, runtime, and security smoke suites pass.
- [ ] **Gate 4 — Release receipt is valid:** `python tools/dev_workflow.py release-check` writes a stable `Ref`, complete gate state, and an explicit `Next Review Step`.

---

## Section B — Library Continuity Scenarios

Gate Owner: **Library feature lead**
Last verified: _____________

Manual smoke scenarios exercised against the current build on Windows. Each scenario starts from a fresh launcher launch unless noted otherwise.

- [ ] **B1 — Root save:** Navigate to Library, add a new approved root folder that exists on disk. Confirm the root appears in the Library surface and no error is shown.
- [ ] **B2 — Item attach:** With at least one root approved, select a file or note from Library and attach it to the active chat session. Confirm the item appears in the chat context indicator before sending.
- [ ] **B3 — Default source pin:** In a workspace with at least one Library item, pin that item as the workspace default. Relaunch the launcher. Confirm the default item is shown as active context without re-attaching manually.
- [ ] **B4 — Workspace switch default persistence:** Set a different default source in two separate workspaces. Switch between the two workspaces. Confirm each workspace loads its own default source and does not show the other workspace's default.
- [ ] **B5 — Remove clears stale default:** Remove the pinned default source from a workspace. Switch to another workspace and back. Confirm the removed default is no longer present and no stale context label is shown in the chat header.
- [ ] **B6 — Context prioritization in compose:** Attach two Library items. Send a chat message. Confirm the outgoing prompt (visible in debug or log output) includes both item titles prepended before the user's request text, in the format produced by `compose_library_aware_message` in `src/guppy/launcher_application/library_workflow.py`.

---

## Section C — Voice Baseline

Gate Owner: **Voice feature lead**
Last verified: _____________

- [ ] **C1 — Push-to-talk activates and transcribes:** Hold-to-talk key activates the microphone, records speech, releases on key-up, and the transcribed text appears in the chat composer without truncation.
- [ ] **C2 — Voice assignment persists across restart:** Assign a non-default voice in the Voices surface. Restart the launcher. Confirm the assigned voice is still selected and plays correctly on the next TTS output.

---

## Section D — First-Run Path

Gate Owner: **UX / Navigation lead**
Last verified: _____________

These scenarios should be run with a clean or reset launcher state (no prior workspace or Library configuration) to validate the first-run experience.

- [ ] **D1 — Primary nav is legible on first launch:** On first launch (no prior state), the four primary destinations — Chat, Workspaces, Library, and Settings — are all visible and labeled in the navigation surface without requiring any scrolling, expansion, or hover.
- [ ] **D2 — Library empty state is clear:** Navigate to Library without any approved roots set. Confirm the empty state copy explains what Library is and has a clear affordance to add a root folder. No error state or blank screen is shown.
- [ ] **D3 — Workspace creation completes without settings knowledge:** Create a new workspace using only the Workspaces surface (no Settings or App Mgmt required). Confirm the new workspace is selectable and the Library surface reflects the new workspace context after switching.

---

## Sign-Off

| Role | Name | Date |
|---|---|---|
| Engineering lead | | |
| Library feature lead | | |
| Voice feature lead | | |
| UX / Navigation lead | | |
| Release approver | | |
