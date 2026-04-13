# M2 Scope Lock & Decision Framework

**Locked:** April 13, 2026  
**Valid Through:** June 15, 2026 (M2 Launch)  
**Amendment Process:** Steering committee approval required; no feature creep without gate

---

## 6 M2 Epics (LOCKED)

| Epic | Owner | Priority | Start | End | Acceptance |
|---|---|---|---|---|---|
| 1. Persona Builder v1 | UI | Highest | Apr 15 | May 6 | Non-technical user defines persona without file editing |
| 2. Model Assignment + Routes | ModelOps | High | Apr 22 | May 13 | Every task type has visible route + fallback chain |
| 3. Voice Library + Assignment | Voice | High | Apr 29 | May 13 | User can assign voice globally, override per-agent |
| 4. Tools Tab Cleanup | Tools | High | Apr 22 | May 6 | No placeholders visible; every control has action |
| 5. Advanced Tab + Recovery | Platform | Medium | May 6 | May 20 | Recovery flows discoverable; outcomes visible; guards working |
| 6. Off-Hours Write Scaling | Runtime | Medium | May 13 | May 27 | 5–10 safe write tasks/week; <3 writes/run budget |

**All must complete by Sep 30, 2026 exit gate.**

---

## MUST DELIVER (Non-Negotiable)

1. **Persona Builder is non-technical-friendly**
   - No JSON editing in MVP
   - Sliders/dropdowns/toggles only
   - Live system prompt preview
   - If user sees `{` or `[`, UX failed

2. **Every user action has a visible outcome**
   - Save persona → message appears in chat or toast
   - Select model → status updates or visual confirmation
   - Play voice sample → audio plays or shows error
   - If silent or "pending...", UX failed

3. **All models must have health status**
   - ✓ Ready, ⚠ Slow, ✗ Offline
   - Updated ≥ every 30s
   - If user can't tell if model is alive, UX failed

4. **Off-hours writes are safe by default**
   - Dry-run staging to `runtime/offhours_results/dry_run/`
   - Human approval required before writing
   - Path validation against whitelist (src/, tests/, docs/, config/ only)
   - If task writes to root or outside workspace, REJECT

5. **Recovery actions are always available**
   - Warmup, Restart, Audit visible in Advanced tab
   - Guards prevent accidental double-launch (e.g., can't start 2nd daemon if one running)
   - If guards fail and user launches duplicate, platform failed

---

## OPTIONAL (May defer to M2.2 if time pressure)

| Feature | If Skipping | Mitigation |
|---|---|---|
| Route Visualizer (flowchart) | Omit 2-week spike; keep click-to-assign only | Add TODO comment; plan for M2.2 |
| ElevenLabs Voice Support | Lock to Kokoro + system TTS only | Document optional support for future |
| Auto-Apply Write Tasks | Require approval for all; no auto-apply | Document auto-apply for M2.2 |
| Voice Playback Interruption Safeguard | Defer if no audio race found | Assume not needed; test well |

---

## STRICTLY OUT OF SCOPE (M3 or Later)

| Item | Why Deferred | Target Milestone |
|---|---|---|
| iOS client | Platform complexity; test on Windows first | M3 or post-launch |
| Live CRM writes (Salesforce, HubSpot) | Integration testing nightmare; skip MVP | M3 or post-launch |
| Shared Memory v1 (Qdrant RAG) | Storage scaling unknown; skip for pilot | M3 or post-launch |
| CI/CD deploy gates (GitHub Actions) | Adds test infrastructure burden | M3 or post-launch |

**Any request for these items must include: business justification, timeline impact, risk analysis, and steering committee sign-off.**

---

## Key Architecture Constraints

### UI Layer
- **No legacy window spawns from default flow**
  - GuppyPrime embedded mode only
  - Standing document: [ui/launcher/DESIGN.md](../ui/launcher/DESIGN.md)
  - Test: `tests/test_launcher_interactions_smoke.py` line 45+

- **Transient state lives in status strip, not chat bubbles**
  - "Processing..." → `assistant_view.set_status()`
  - Not → `add_system_message()`
  - Standing document: [memory/repo/ui-streaming-convention.md](/memories/repo/ui-streaming-convention.md)

### Tools & API
- **Off-hours write budget: max 3 files/run**
  - Hard cap in `tools/idle_agent_worker.py` line 533–545
  - Exceeding budget auto-downgrades to dry-run
  - No override flag

- **Path validation mandatory for all writes**
  - Whitelist: `src/`, `tests/`, `docs/`, `config/` only
  - Blacklist: root, `guppy_core/`, `ui/launcher/`
  - Function: `_safe_write_path()` in idle_agent_worker.py

### guppy_core Package
- **No breaking changes to tool_registry exports**
  - All 77 tools must remain importable
  - Standing document: [guppy_core/__init__.py](../guppy_core/__init__.py) line 1–25

- **No new top-level modules in guppy_core/**
  - Only add to existing 7: tool_metrics, system_prompt, tool_registry, tool_runner, debug_flags, beta_policy, network_utils
  - Amendment requires architecture review

---

## Decision Points with Recommendations

### Decision 1: Model Selection UX (Drag-Drop vs Click-to-Assign)
**DECIDED:** Click-to-assign (dropdown + apply button)  
**Reasoning:** MVP simpler, less state complexity, no animation bugs  
**Revisit in:** M2.2 if UX feedback signals demand

### Decision 2: Voice Engine Coverage (Kokoro + System only vs Add ElevenLabs)
**DECIDED:** Lock to Kokoro + Windows system TTS in M2.0  
**Reasoning:** Fewer API keys, less maintenance, good coverage for pilot  
**Revisit in:** M2.2 after M2.0 stability + user demand signal

### Decision 3: Off-Hours Task Approval (Always require vs Auto-apply <5-line)
**DECIDED:** Always require human approval in M2.0  
**Reasoning:** Safety-first; human review catches edge cases; confidence-building  
**Revisit in:** M2.2 after 20+ successful approved tasks demonstrate reliability

### Decision 4: Forms State Management (Qt State Machine vs Simple Flags)
**DECIDED:** Simple flags in Python (class variables)  
**Reasoning:** Faster to implement; less learning curve for team  
**Risk:** May need refactor if state becomes complex (recursive editing?). Mitigate: unit test state transitions weekly.

---

## Blocking Depdencies (Must Exist by Jun 15)

| Dependency | Current Status | Owner | Due |
|---|---|---|---|
| `/status` API endpoint (model health) | ✓ Exists in guppy_api.py | Platform | ✓ Ready |
| Model routes schema (`config/model_routes.json`) | ✓ Exists + validated | ModelOps | ✓ Ready |
| Persona config schema (`config/personas.json`) | ✓ Exists + validated | UI | ✓ Ready |
| Voice bindings schema (`runtime/voice_bindings.json`) | ✓ Exists | Voice | ✓ Ready |
| Kokoro inference working | ✓ Tested at baseline | Runtime | ✓ Ready |
| Merlin-code model responsive | ✓ Tested | Runtime | ✓ Ready |
| System TTS fallback working | ✓ Tested on Windows | Voice | ✓ Ready |
| `apply_patch` tool ready | ✓ In tool_registry + handler | Platform | ✓ Ready |
| Off-hours worker task queue | ✓ Exists; accepts write tasks | Runtime | ✓ Ready |

**All green. No blocking dependencies remain.**

---

## Weekly Gate Reviews (Every Mon 10am)

Each week, review:
1. **Are we on schedule?** (Burndown vs plan)
2. **Have we discovered new risks?** (If yes, update Risk table)
3. **Do we need to defer any optional features?** (If yes, document + rescope)
4. **Are we violating any constraints?** (If yes, escalate immediately)

If > 2 gates fail, pause feature work and re-plan.

---

## Commit Protocol

Every M2 commit must include:
1. **Related epic** (e.g., `[Epic 1: Persona Builder]`)
2. **Acceptance criteria verified** (if applicable)
3. **Tests passing** (e.g., `70 tests passing`)
4. **No new lint errors** (linter clean)

Example:
```
[Epic 1: Persona Builder] Add tone slider + preview modal

- Slider events wired to live system prompt preview
- Preview modal shows how tone affects Merlin prompts
- Save button persists to config/personas.json
- Tests: form instantiation + slider responsive (2 new tests)
- Status: All 70 tests passing, no lint errors
```

---

## Escalation Path

**If you find a scope violation, blocker, or constraint conflict:**

1. **Email:** Attach evidence (test output, code snippet, decision doc reference)
2. **Cc:** Architecture + Product leads
3. **Subject:** `[M2 SCOPE ALERT] <title>`
4. **Include:**
   - What constraint was violated (reference this doc)
   - Why it happened
   - Proposed resolution (keep, defer, amend, exception)
   - Impact estimate (lines of code affected, days of delay)

**Expected response:** < 4 hours (working hours)

---

## Handoff to Next Phase (Oct 1)

On Sep 30, document:
1. **What shipped:** All 6 epics summary
2. **What deferred:** Any M2.2 features + justification
3. **What broke:** Any technical debt or regressions
4. **What next:** Immediate M3 priorities

Store in: `docs/M2_EXIT_REPORT.md`

---

## EOF — M2 SCOPE LOCKED

**Approved:** Architecture Review + Product Lead  
**Lock Date:** April 13, 2026  
**Breakpoints:** Weekly (every Mon); gate reviews (every Wed)  
**Escalation:** Email arch + product leads with `[M2 SCOPE ALERT]` tag
