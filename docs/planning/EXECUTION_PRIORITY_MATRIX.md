# Execution Priority Matrix — 2026-04-25

## 🎯 Three Parallel Workstreams

```
╔════════════════════════════════════════════════════════════════════════╗
║                   P6 FREEZE-READINESS (BLOCKER)                        ║
║                      Deadline: June 12, 2026                            ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  CRITICAL PATH #1: WEB ↔ DESKTOP PARITY                                ║
║  ├─ Effort: 3–4 weeks (investigation + fixes)                          ║
║  ├─ Risk: HIGH (P6 gate blocker)                                       ║
║  ├─ Owner: Full-stack engineer                                         ║
║  └─ Tasks:                                                              ║
║     1. Audit model inventory (Ollama + cloud) sync (1 week)            ║
║     2. Fix workspace state persistence (1 week)                        ║
║     3. Validate tool/connector no-duplicate rule (3 days)              ║
║     4. Route switching sync across surfaces (1 week)                   ║
║                                                                          ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  CRITICAL PATH #2: CHAT STABILITY + FALLBACK ROUTING                   ║
║  ├─ Effort: 2–3 weeks (design + implementation)                        ║
║  ├─ Risk: MEDIUM (affects daily UX but not acceptance)                 ║
║  ├─ Owner: Backend + frontend engineer                                 ║
║  └─ Tasks:                                                              ║
║     1. Build queue + retry logic (1 week)                              ║
║     2. Add token refresh hooks (3 days)                                ║
║     3. Error recovery UI (chat banner + retry button) (3 days)         ║
║     4. Test fallback chains (local → cloud-tier1 → tier2) (3 days)     ║
║                                                                          ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  CRITICAL PATH #3: ROUTER FOUNDATION (ENHANCEMENT)                     ║
║  ├─ Effort: 4–6 weeks (Phases 1–5)                                     ║
║  ├─ Risk: LOW (new feature, no blocking dependencies)                  ║
║  ├─ Owner: Backend engineer (infra-focused)                            ║
║  └─ Timeline:                                                           ║
║     Phase 1: Provider abstraction + heuristic router (Week 1–2)        ║
║     Phase 2: Wire into chat (Week 3)                                   ║
║     Phase 3: Metrics dashboard (Week 4)                                ║
║     Phase 4: Agent spawning (Week 5–6)                                 ║
║     Phase 5: ML cost optimizer (Ongoing after Phase 3)                 ║
║                                                                          ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  BONUS TRACK: THEME SKINS (COSMETIC)                                   ║
║  ├─ Effort: 1 week (lightweight CSS)                                   ║
║  ├─ Risk: NONE (purely visual)                                         ║
║  ├─ Owner: Frontend designer or junior engineer                        ║
║  └─ Timeline:                                                           ║
║     - Occult Dark theme CSS (1 day)                                    ║
║     - Rock Mag theme CSS (1 day)                                       ║
║     - Gonzo Dark theme CSS (1 day)                                     ║
║     - Settings UI + testing (2 days)                                   ║
║                                                                          ║
╚════════════════════════════════════════════════════════════════════════╝
```

---

## 📊 Dependency Map

```
                    P6 GATES (June 12)
                         ↓
        ┌────────────────┬────────────────┐
        ↓                ↓                ↓
   [PARITY]        [STABILITY]      [FREEZE]
   (3–4 wks)       (2–3 wks)        (ongoing)
        ↓                ↓                ↓
   Web ↔ Desktop   Chat Routing     FR-C4–C10
   Model Sync      + Fallback       tranches
   Workspace Sync  Error Recovery
        │                │                │
        └────────────────┴────────────────┘
                         ↓
                  [RELEASE v1.0]
                   June 12, 2026
                   
                   
        ┌──────────────────────────────────┐
        ↓                                   ↓
   [ROUTER] (June 30)              [THEMES] (May 1)
   (4–6 weeks, parallel)           (1 week, lightweight)
        │                                   │
   Phase 1–5:                      Occult/Rock/Gonzo
   - Provider abstraction           added to Settings
   - Task router + intent           ✓ Independent work
   - Metrics dashboard
   - Agent spawning
   - Cost optimizer
        │
   [POST-RELEASE ENHANCEMENT]
   Available for v1.1 or integrated
   if completed by June 12
```

---

## ⏱️ Recommended Weekly Schedule

### Week 1 (Apr 25–May 1)
| Task | Owner | Hours | Status |
|------|-------|-------|--------|
| **Parity audit** (model + workspace inventory) | Full-stack | 40 | 🔴 START |
| **Theme CSS prep** (color extraction) | Designer | 16 | 🟢 START |
| **Router Phase 1 design** (providers, task router) | Backend | 24 | 🟡 SKETCH |

**Milestones:** 3 issues identified in parity audit; color palettes extracted; router design reviewed

---

### Week 2–3 (May 2–15)
| Task | Owner | Hours | Status |
|------|-------|-------|--------|
| **Parity fixes** (model sync, workspace state) | Full-stack | 80 | 🔴 IN PROGRESS |
| **Chat stability** (queue + retry logic) | Backend+Frontend | 80 | 🔴 IN PROGRESS |
| **Theme CSS implementation** | Designer | 24 | 🔴 IN PROGRESS |
| **Router Phase 1** (provider abstraction) | Backend | 40 | 🔴 IN PROGRESS |

**Milestones:** Parity passing locally; themes in Settings; router tests passing

---

### Week 4–5 (May 16–29)
| Task | Owner | Hours | Status |
|------|-------|-------|--------|
| **Parity validation across surfaces** | QA | 40 | 🔴 TEST |
| **Chat fallback testing** | QA | 40 | 🔴 TEST |
| **Router Phase 2** (wire into chat) | Backend+Frontend | 40 | 🔴 IN PROGRESS |
| **Router Phase 3** (metrics dashboard) | Frontend | 40 | 🔴 IN PROGRESS |

**Milestones:** All P6 gates passing; router routing live; metrics visible

---

### Week 6 (Jun 1–12)
| Task | Owner | Hours | Status |
|------|-------|-------|--------|
| **Freeze-readiness audit** (FR-C4–C10) | Full team | 80 | 🔴 IN PROGRESS |
| **Router Phase 4** (agent spawning) | Backend | 40 | 🟡 STRETCH |
| **Release candidate build** | DevOps | 16 | 🔴 START |

**Milestones:** June 12 release candidate ready; router stretch goals met if time allows

---

### Week 7+ (Post-Release)
| Task | Owner | Hours | Status |
|------|-------|-------|--------|
| **Router Phase 5** (ML cost optimizer) | ML engineer | 80 | 📋 BACKLOG |
| **Theme variants** (custom color packs) | Designer | 40 | 📋 BACKLOG |

---

## 🎯 Critical Success Factors

### For Parity Validation
- ✅ Model list returns same results from `/api/models` and launcher's Ollama SDK
- ✅ Workspace state (chat history, selected models, settings) persists across launcher ↔ web ↔ API
- ✅ No duplicate tool inventories (tools API returns same list to both surfaces)
- ✅ Route switching syncs: if user switches to Cloud in web, launcher reflects it

### For Chat Stability
- ✅ In-flight requests survive provider switch (queue + retry)
- ✅ Token refresh doesn't drop ongoing conversation
- ✅ Fallback chain executes on timeout (local 5s → cloud 30s)
- ✅ User sees provider badge + can force re-route via UI

### For Router Foundation
- ✅ Phase 1: Provider abstraction 100% tested locally
- ✅ Phase 2: Chat routing live with user preference toggle
- ✅ Phase 3: Metrics accurate (no off-by-one cost errors)
- ✅ Phase 4: Agent spawning works for COMPLEX tasks

### For Themes
- ✅ All 5 themes WCAG AA compliant (4.5:1 text contrast)
- ✅ No broken layouts on mobile
- ✅ Theme persists across reload (localStorage + Settings DB)
- ✅ Smooth fade-in transition on switch

---

## 🚦 Go/No-Go Checklist (June 12)

### P6 Acceptance Criteria
- [ ] **Parity:** Web UI model list == Desktop launcher model list ✓
- [ ] **Parity:** Workspace state syncs across surfaces ✓
- [ ] **Stability:** Chat handles local→cloud failover gracefully ✓
- [ ] **Stability:** Token refresh doesn't drop conversation ✓
- [ ] **Statistics:** Tool counts, model availability accurate ✓
- [ ] **PC Control:** Guarded and calm (no competing center) ✓
- [ ] **North-star:** Chat/Workspaces/Library/Settings primary ✓
- [ ] **Dual surface:** No inventory conflicts ✓

### Nice-to-Haves (If Time Allows)
- [ ] Router Phase 1–2 complete (routing logic live)
- [ ] Router Phase 3 live (metrics dashboard)
- [ ] Themes in Settings (cosmetic skins)

**If all P6 + nice-to-haves complete: Ship June 12 🚀**  
**If P6 complete but router/themes incomplete: Ship June 12, plan v1.1 for July 🚀**

---

## 📞 Team Assignments (Proposed)

- **Full-stack engineer:** Parity audit + fixes (critical path)
- **Backend engineer:** Chat stability + router foundation (parallel tracks)
- **Frontend engineer:** Chat UI updates + metrics dashboard (Phase 3)
- **QA engineer:** Parity validation, fallback testing, integration testing
- **Designer/Junior Frontend:** Theme CSS + Settings UI
- **DevOps:** Release build, testing automation

**Estimated headcount:** 1.5 FTE for full delivery by June 12; 2 FTE for stretch goals

---

## 🎓 Lessons Learned & Open Questions

1. **Should parity validation start before architecture changes?**
   - *Recommendation:* Yes. Audit first (3 days), then design fixes.

2. **Router design: Service mesh vs. in-process?**
   - *Current plan:* In-process (simpler, no ops overhead). Service mesh (solo.io) if we scale to 50+ endpoints.

3. **Theme updates: Ship all 5 at once or stagger?**
   - *Current plan:* Ship all 5 simultaneously (low risk, better UX).

4. **Cost tracking: Real-time or batch billing integration?**
   - *Current plan:* Batch + daily email report. Real-time if we add user credits system.

5. **Agent spawning: Use existing agents or new AgentV2 system?**
   - *Current plan:* Wrap existing agent framework. Refactor if too much glue code.

---

**Status: Ready for assignment. No blockers identified on implementation side.**
