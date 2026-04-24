# Tranche 53 Goals And UI Audit

Date: April 20, 2026

Scope:
- Repo-grounded baseline for `PL-C8`
- Current shell and hub review against Guppy's stated pre-launch goals
- Focused on shipped launcher code, not aspirational mocks

North-star goals checked:
1. Calm chat-first desktop assistant
2. First useful success in under 5 minutes
3. Grandma-readable screens with progressive disclosure
4. Stable launcher startup and clear failure messaging
5. Unified ownership across Home, Models, Tools, Library, and Settings

## Summary

Overall state: `partial pass`

Strengths:
- Five-hub ownership is now clear and stable.
- Home remains visibly chat-first.
- Settings already owns provider/account/API-key work.
- Tools and Library now explain purpose better than earlier launcher revisions.

Current blockers and gaps:
- The launcher had no visible topbar startup/readiness cue before this pass.
- The topbar `CHAT` control was wired to Workspaces instead of chat context behavior.
- Home drawer behavior was not truthful: the toggle path could not open it on Home.
- First-run wizard logic exists in `src/guppy/launcher_application/first_run_wizard.py` but is not yet surfaced as a first-class launcher onboarding experience.
- Smaller-window readability is improved but not yet consistently audited across every hub.

## Hub Matrix

### Home
- Goal fit: `pass`
- Notes: chat-first structure is good; active context and starter copy are understandable.
- Gap: launcher context controls still need a simpler and more visible first-run/readiness story.

### Models
- Goal fit: `partial pass`
- Notes: model/runtime ownership is correct and the topbar summary helps.
- Gap: local runtime readiness still reads like a power-user lane more than a guided first-success flow.

### Tools
- Goal fit: `partial pass`
- Notes: tool traces, blocking reasons, and Settings remediation are much stronger now.
- Gap: a full command-language audit is still pending under `PL-C13`.

### Library
- Goal fit: `pass`
- Notes: note editing, media support, and `USE IN CHAT` flow are coherent.
- Gap: no major blocker from this pass.

### Settings
- Goal fit: `partial pass`
- Notes: ownership is correct and credential/provider work is centralized.
- Gap: provider lifecycle still needs stronger "install, verify, reconnect, remove" onboarding polish.

## First-Run Contract Check

Current contract state: `not yet launcher-complete`

What exists:
- Track 1 install readiness
- Track 2 local model readiness
- Track 3 first-request verification

What is still missing:
- launcher-visible first-run wizard surface
- guided first-success sequencing in the visible desktop flow
- plain-language install-vs-local-model path choice at startup

## Immediate execution moves opened by this audit

1. Make shell state truthful: show runtime/startup state in the topbar.
2. Make chat context controls truthful: route `CHAT` into actual Home drawer behavior.
3. Start writing implementation deltas against Stitch and inspiration references.
4. Follow with smaller-window and tooltip sweeps across all hubs.
