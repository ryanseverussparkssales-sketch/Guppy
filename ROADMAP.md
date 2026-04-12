# Roadmap and Handoff

Last updated: April 12, 2026

This file is the working document for active priorities and handoff notes. `README.md` holds the stable project snapshot. This file should stay short and be updated during active implementation.

## Current Focus: Multi-Phase Smart Dispatcher Implementation

**Strategic Direction**: Replace Ollama bottleneck with task-aware smart dispatcher. Guppy is a personal butler/assistant (not a sales tool). Priorities are: **fast response (<3s), right model first time, seamless voice, predictable latency**.

### Phase 1: Smart Dispatcher Core (Haiku-First) ← **STARTING NOW**

**Objective**: Make Guppy 5-10x faster and predictable. Replace local Ollama blocking with intelligent Claude routing.

- Task classification heuristics (find, build, explain, write, qualify via simple regex/keyword matching)
- Route "simple" queries to Haiku (2-3s)
- Route "complex" queries to Sonnet (5-10s)
- Route "teaching" queries to Merlin/Ollama (Socratic, free, local)
- Proper fallback: Haiku (timeout 3s) → Sonnet (if needed) → Ollama (if offline)
- Status: **In progress** (starting Phase 1)

### Phase 2: Fallback Chain & Offline Handling

**Objective**: No more random 30s timeouts. Predictable chain.

- Fix fallback logic so Haiku timeout doesn't re-try Ollama
- Auto-detect offline mode → fallback to Ollama-only
- Status: **Pending** (after Phase 1)

### Phase 3: Merlin Smart Routing

**Objective**: Make Merlin part of daily use, not separate window.

- Auto-route "explain", "teach", "help me understand" to Merlin
- Optional parallel mode: "explain X and research X" → Merlin + Sonnet in parallel
- Status: **Pending** (after Phase 1-2)

### Phase 4: Voice Integration Tuning

**Objective**: Wake-word triggers fast-path dispatcher. Voice feels responsive.

- Wake-word → fast-path Haiku (2-3s)
- TTS reads response smoothly (no waiting on Ollama)
- Status: **Pending** (after Phase 1, parallel possible)

### Phase 5: Memory & Context Caching

**Objective**: Repeated questions are instant. Reduce API calls.

- Task-type based caching (similar queries reuse recent results)
- Semantic memory integration
- Status: **Pending** (after Phase 1-2)

### Phase 6: Foundation Work (Visibility & Reliability)

**Objective**: Make system debuggable and reliable. Prepare for scaling.

- Make `inference_router.py` the single inference path (UIs call it, no bypasses)
- Structured logging: every request logs task type, model chosen, latency, cost
- Metrics dashboard: integrate router events into `runtime/agent_performance.jsonl`
- Fix streaming: Sonnet results stream like Ollama (not batch)
- Status: **Pending** (parallel with Phases 1-5)

## Related Goals (Aligned with Phases)

### Remote Hardening

- **Blocked by**: Phase 1 (need fast latency for remote to feel snappy)
- **Unblocked by**: Phase 1 → Haiku-first makes tunnel latency acceptable

### Status / Context Performance

- **Blocked by**: Phase 5 (caching) + Phase 6 (logging)
- **Improved by**: Phase 1 (fewer Ollama waits)

### Butler Workflow Depth (Not CRM sales)

- **Personal tasks** example: "Remind me to call X at 3pm", "Draft email to Y", "What's on my calendar tomorrow?"
- Use Merlin for drafting (Socratic) + Guppy-Haiku for quick lookups
- Use Merlin for explaining/teaching (uncommon, but intentional)
- Status: **In design** (enabled by Phase 1-3)

### Release Discipline

- **Blocked by**: Phase 6 (metrics and reliability foundation)
- **Improved by**: All phases (predictable performance)

### Voice and Wake-Word Tuning

- **Blocked by**: Phase 1 (need fast response to feel natural)
- **Enabled by**: Phase 4 (fast-path voice dispatch)

## Open Questions

- Should Phase 1 dispatcher be invisible (just use router), or add "Smart Mode" toggle to Guppy UI?
- After Phase 1, which butler workflow should we validate first: task reminders, email drafting, or calendar queries?
- Should Merlin enable cloud fallback in Phase 3, or stay local-only for cost reasons?

## Handoff Rules

- Add new notes at the top of the handoff log.
- Keep entries short and factual.
- Record what changed, what was verified, and what still needs follow-up.
- Do not create another status markdown file for routine session notes.

## Handoff Log

### 2026-04-12 (Latest)

**Strategic Shift: Smart Dispatcher for Butler/Assistant UX**

- Analyzed current system: Ollama bottleneck is killing latency; inference router exists but UIs bypass it; Merlin unused (requires manual selection).
- Reframed priorities away from CRM/sales workflows toward butler/personal assistant: fast (<3s), accurate, transparent, integrated voice.
- Designed 6-phase implementation plan:
  - Phase 1 (Starting): Smart dispatcher core (task classification → Haiku for simple, Sonnet for complex, Merlin for teaching)
  - Phase 2: Fallback chain fix (no more random 30s timeouts)
  - Phase 3: Merlin smart routing (auto-detect teaching tasks)
  - Phase 4: Voice fast-path tuning (wake-word triggers quick response)
  - Phase 5: Memory/caching (repeated questions instant)
  - Phase 6: Foundation (logging, metrics, streaming, single inference path)
- Aligned phases with existing roadmap goals: remote hardening unblocked by Phase 1 latency improvement; butler workflows enabled by Phase 1-3; release discipline enabled by Phase 6.
- Identified that monetization is secondary; butler experience is primary. Foundation for future fine-tuning and scaling built into architecture.

### 2026-04-12

- Decided to keep `docs/TROUBLESHOOTING.md` and `docs/PACKAGING.md` as standalone runbooks, while folding short operational summaries into `README.md`.
- Archived `docs/FEATURES.md` to `docs/archive/reference-history/FEATURES.md`; kept `docs/API.md` and `docs/VOICE.md` as focused operational references.
- Kept `CONTRIBUTING.md` in the repo root by convention and moved `PACKAGING.md` to `docs/PACKAGING.md` to reduce root noise.
- Moved older planning and reference docs from `docs/` into `docs/archive/planning-history/`.
- Moved older session, review, milestone, and one-off briefing docs out of the repo root into `docs/archive/root-history/`.
- Added archive notices to older handoff and completion docs so they no longer compete with the living-doc pair.
- Folded the most useful API and voice operational details into `README.md`.
- Current living docs remain `README.md` and `ROADMAP.md` only.

### 2026-04-12

- Condensed living status docs down to `README.md` and `ROADMAP.md`.
- Rewrote `README.md` as the primary source of truth for architecture, setup, current state, and active priorities.
- Rewrote `ROADMAP.md` as the active work board plus handoff log for multi-agent sessions.
- Fixed Guppy UI streaming crash in `guppy_ui.py` by initializing streamed label text state and falling back safely when appending.
- Confirmed the repo already contains the API surface, web client alpha, smoke tests, semantic memory, hub logging, wake-word path, and CRM/VoIP scaffolding.
- Remaining high-value gaps: external remote validation, `/status` latency, packaging hardening, and one complete revenue workflow.

## Next Update Template

Use this format for the next entry:

```text
### YYYY-MM-DD
- Changed:
- Verified:
- Follow-up:
```
