# Guppy Strategic Assessment — 2026-04-25
## Roadmap Status → Cloud-Local Integration → Theme Skins

---

## 🎯 ROADMAP STATUS

### Current Phase: **P6 Platform Hardening (TR55+)** — ACTIVE
- **Release validation:** ✅ PASS (all 8 gates green)
- **Web UI integration:** ✅ LANDED (TR54+, Atoll Editorial, Tailwind v4, Vite)
- **Deadline:** June 12, 2026 (Freeze-readiness gates)

### Progress Snapshot
| Component | Status | Detail |
|-----------|--------|--------|
| **Architecture** | ✅ INTACT | Five-hub launcher verified; no drift |
| **Chat (Home)** | ⚠️ IN PROGRESS | Stable local/cloud routing needed |
| **Models (MAIN/SUB)** | ⚠️ IN PROGRESS | Parity validation with web UI pending |
| **Tools** | ✅ WIRED | SQLite registry working; enable/disable functional |
| **Settings** | ✅ WIRED | Provider switching, model selection active |
| **Web UI** | ✅ INTEGRATED | Full Atoll Editorial design, TanStack Query |
| **Desktop Launcher** | ✅ VERIFIED | Qt + Ollama functioning |

### Near-term Milestones (This Month)
1. **Web UI parity validation** (🔴 CRITICAL BLOCKER) — P6 acceptance gate
2. **Stable chat with fallback routing** (⚠️ IN PROGRESS)
3. **Model switching sync** across launcher/web/API (⚠️ IN PROGRESS)
4. **Freeze-readiness tranches** FR-C4 through FR-C10 (📋 QUEUED)

---

## 🚨 CURRENT BLOCKERS

### 🔴 P6 Critical Blockers

#### 1. **Web UI ↔ Desktop Launcher Parity**
- **Problem:** Web UI must use shared model inventory, workspace state, route contracts with launcher
- **Impact:** P6 acceptance gate; blocks freeze-readiness validation
- **Required validation:**
  - ✓ Model list (Ollama + cloud) same across both surfaces
  - ✓ Workspace state persisted in shared DB
  - ✓ Route switching (local → cloud) syncs across launcher/web/API
  - ✓ No duplicate tool/connector inventories
- **Effort:** 2–3 days investigation + 1 week fixes

#### 2. **Cloud-Local Routing Logic**
- **Problem:** Current system handles local (Ollama) OR cloud, but not intelligent switching
- **Impact:** Can't use fast local for simple tasks, expensive cloud for complex ones
- **Missing:** 
  - Task complexity detection
  - Provider selection rules (speed vs. cost vs. capability)
  - Fallback chains (local fails → cloud tier 1 → tier 2)
  - Cost tracking per provider
- **Effort:** 2–3 weeks design + implementation

#### 3. **Chat Stability Under Route Changes**
- **Problem:** Provider switching mid-conversation, auth refresh, availability changes
- **Impact:** Daily users experience chat dropouts
- **Missing:**
  - Queue + retry logic with exponential backoff
  - In-flight request handling on provider switch
  - Token refresh hooks
  - Error recovery UI
- **Effort:** 1–2 weeks implementation

#### 4. **Statistics Accuracy**
- **Problem:** UI shows placeholder counts instead of runtime truth
- **Impact:** Users can't trust model/tool availability indicators
- **Missing:**
  - Real-time cache of available models
  - Tool enable/disable state from DB
  - Latency metrics per provider
- **Effort:** 1 week implementation

---

## 🔗 CLOUD-LOCAL INTEGRATION STRATEGY

### Research Summary: 2026 Sources

From your research links, the consensus on hybrid cloud-local LLM systems:

#### Key Patterns (Reddit + Blog Analysis)
1. **Entry Point:** Local small models (7B–13B) handle 60–80% of tasks, cloud for remaining 20–40%
2. **Economics:** Local inference $0.00/token (amortized), cloud $0.0001–$0.001/token depending on provider
3. **Speed Hierarchy:** Local <50ms latency, cloud-regional ~200ms, cloud-standard ~500ms+
4. **Routing Decision Tree:**
   - Task complexity (token budget, reasoning depth) → model class selector
   - User preference (speed vs. cost) → tier selector
   - Availability (local running?) → fallback chain

#### Best Practices (Routing & Infrastructure)
- **Solo.io pattern:** Service mesh with intent-based routing (policy-driven, not hard-coded)
- **BentoML pattern:** Multi-cloud inference with response latency tracking; circuit breaker pattern for provider health
- **Academic (arXiv 2603.04445):** Agent spawning per task type; dynamic model selection based on context length + reasoning needs
- **Multi-LLM Provider routing:** Sequential filtering:
  1. Filter by capability (reasoning, coding, vision)
  2. Filter by cost band (user budget)
  3. Select by latency SLA
  4. Apply fallback chain

#### Hybrid Architecture Recommendations
- **Local tier (always available):** 7B model (e.g., `qwen2.5:7b` at ~5GB) for chat-like tasks, summaries, lightweight analysis
- **Cloud tier 1 (fast, affordable):** Claude Haiku ($0.00035/token) or Qwen-cloud for medium tasks
- **Cloud tier 2 (expensive, powerful):** Claude Opus or GPT-4 for complex reasoning, code, multi-step tasks
- **Decision logic:** Simple heuristic + ML-based confidence scoring over time

---

## 🎯 PROPOSED: Guppy Cloud-Local Central Mind

### Architecture: Three-Tier Routing with Agent Spawning

```
User Input (Chat, Tool, Analysis)
         ↓
  [Task Router]
    ├─ Extract intent, token budget, reasoning depth
    ├─ Check user preference (speed vs. cost)
    └─ Classify: SIMPLE | MEDIUM | COMPLEX | SPECIALIZED
         ↓
    [Availability Check]
    ├─ Local Ollama running?
    ├─ Cloud provider auth valid?
    └─ User has budget remaining?
         ↓
    [Tier Selection]
    ├─ SIMPLE (chat, factual) → Try LOCAL first (qwen-fast:7b)
    ├─ MEDIUM (analysis, coding) → Try CLOUD-TIER1 (Haiku, Qwen)
    ├─ COMPLEX (reasoning, design) → Try CLOUD-TIER2 (Opus, GPT-4)
    └─ SPECIALIZED (vision, audio) → Cloud-tier2 only
         ↓
    [Execute + Fallback Chain]
    ├─ Primary tier: execute with timeout (local 5s, cloud 30s)
    ├─ On failure/timeout: next tier in chain
    ├─ On success: log latency, cost, quality metrics
    └─ Return to user with routing metadata
```

### Key Features

#### 1. **Task Router**
- Parse user input for complexity signals
  - Token count estimate
  - Reasoning depth (single-turn vs. multi-step)
  - Special requirements (code, structured output, etc.)
- Return routing intent + confidence

#### 2. **Provider Abstraction**
- Unified interface: `Provider.infer(prompt, max_tokens, temperature, ...)`
- Implementations: `LocalProvider` (Ollama), `AnthropicProvider`, `OpenAIProvider`, `CohereProvider`, `MistralProvider`
- Each tracks: availability, latency, cost, error rate

#### 3. **Fallback Chains**
- User defines preference: `prefer_speed`, `prefer_cost`, `prefer_quality`
- Router builds chain:
  - `prefer_speed`: [local, cloud-regional, cloud-std]
  - `prefer_cost`: [local, haiku, gpt-3.5]
  - `prefer_quality`: [opus, gpt-4, local-fallback]
- Circuit breaker: if provider fails 3x → skip to next

#### 4. **Metrics & Learning**
- Track per task:
  - **Input:** task type, complexity score, selected provider
  - **Output:** latency, cost, quality (user feedback), success/fail
- Use metrics to refine router:
  - ML model learns which complexity → provider mapping is best
  - Cost optimizer suggests tier switches
  - Quality scorer detects when local ≈ cloud (save money)

#### 5. **Agent Spawning**
- For COMPLEX + SPECIALIZED tasks, spawn single-use agent:
  - Agent gets: full context, best provider, extended token budget
  - Agent performs: planning, sub-task decomposition, multi-step reasoning
  - Agent reports: final answer + reasoning trace
- Example: "Draft a full marketing campaign for Q3" → spawn agent with Opus, 200K context

---

## 📋 EXECUTION PLAN: Cloud-Local Integration (4–6 weeks)

### Phase 1: Foundation (Week 1–2)
**Objective:** Build routing infrastructure without changing user experience

**Tasks:**
- [ ] Create `providers/` package with abstract `Provider` base class
- [ ] Implement `LocalProvider` (Ollama HTTP client) + testing
- [ ] Implement `AnthropicProvider`, `OpenAIProvider` stubs
- [ ] Build `TaskRouter` with intent detection (simple heuristic)
- [ ] Create `RouteChain` executor with fallback logic
- [ ] Add metrics collection: latency, cost, success/fail logs

**Deliverable:** Routing engine fully tested; no UI changes yet

**Effort:** 1 developer-week

---

### Phase 2: Wire Into Chat (Week 3)
**Objective:** Route chat messages through new system; keep UX identical

**Tasks:**
- [ ] Refactor `chat/routes.ts` → use routing engine
- [ ] Add user preference picker (Settings → Advanced → Routing)
  - Radio buttons: "Fast (local)", "Balanced (smart)", "Quality (cloud)"
- [ ] Update chat message handler:
  - Extract intent from user message
  - Route to appropriate provider
  - Display provider badge ("🔵 Local" / "☁️ Claude" / etc.)
- [ ] Test fallback: local fails → cloud succeeds

**Deliverable:** Chat fully routed; parity maintained with existing behavior

**Effort:** 1 developer-week

---

### Phase 3: Metrics Dashboard (Week 4)
**Objective:** Show user the routing decisions & costs

**Tasks:**
- [ ] Create `Admin → Routing & Metrics` view:
  - This week's provider usage (pie chart)
  - Cost summary (local $0 + cloud cost)
  - Latency histogram (local vs. cloud)
  - Success rate per provider
- [ ] Wire metrics table: recent chats → provider + latency + cost
- [ ] Add inference timeout tuning (user-settable per tier)

**Deliverable:** Transparent routing visibility; user can tune preferences

**Effort:** 1 developer-week

---

### Phase 4: Agent Spawning (Week 5–6)
**Objective:** Enable complex tasks to use agent pattern

**Tasks:**
- [ ] Detect when user task is COMPLEX (>500 tokens estimate, multi-step signals)
- [ ] Spawn single-use Agent:
  - Clone router but lock to best tier
  - Extended token budget (200K+ for complex reasoning)
  - Access to planning + tool-use
- [ ] Agent lifecycle:
  - Plan phase: decompose task
  - Execution phase: sub-tasks with fallback chains
  - Reporting phase: final output + reasoning trace
- [ ] UI: show agent status (planning, executing, done)

**Deliverable:** Complex tasks route to dedicated agents; planning visible

**Effort:** 1.5 developer-weeks

---

### Phase 5: Cost Optimizer (Ongoing)
**Objective:** Suggest tier switches when local ≈ cloud quality

**Tasks:**
- [ ] ML model: train on (task_type, provider, quality_score) → predict quality
- [ ] Optimizer suggests: "This task type works just as well on local; save $X per month"
- [ ] User can accept → auto-route to local next time
- [ ] Monthly report: "You saved $X by smart routing"

**Deliverable:** ML-informed routing; cost transparency

**Effort:** 2 developer-weeks (ongoing; can defer to Phase 2 completion)

---

### Gating & Rollout
- **Gate 1:** Phase 1 + 2 = parity chat experience ✓
- **Gate 2:** Phase 3 = transparent metrics ✓
- **Gate 3:** Phase 4 = agent spawning working ✓
- **Gate 4:** Phase 5 = cost optimization live ✓
- **P6 inclusion:** Phase 1–3 required by June 12; Phase 4–5 stretch goal

---

## 🎨 THEME SKINS: Adding Cosmetic Variations

### Current System Architecture
```
web/src/
├── themes/
│   ├── index.ts           # Theme registry + applyTheme() hook
│   ├── dark.css           # Dark theme override ([data-theme="dark"])
│   └── (implicit: light theme in index.css @theme block)
├── index.css              # @theme block (never edit) + imports dark.css
└── SettingsView.tsx       # Appearance card + useTheme() hook
```

### How Themes Work
1. **Base variables** defined in `index.css` `@theme` block (CSS custom properties)
2. **Theme overrides** via `[data-theme="id"]` selector (e.g., `[data-theme="occult"]`)
3. **Activation:** `applyTheme(id)` → sets `document.documentElement.dataset.theme = id`
4. **Persistence:** localStorage + Settings DB

### Three New Skins: Color Mappings

#### 🌙 **Occult Dark**
| Element | Light (Current) | Occult Dark |
|---------|---------|---------|
| Background | `#ffffff` | `#020103` (abyss) |
| Surface | `#f3f4f6` | `#08050a` (void) |
| Primary (accent) | `#3b82f6` (blue) | `#c41e1e` (crimson) |
| Secondary | `#8b5cf6` (purple) | `#8b0000` (blood) |
| Text primary | `#1f2937` | `#ead0cc` (vellum) |
| Text secondary | `#6b7280` | `#a8a0b8` (silver) |
| Accent (highlights) | `#fbbf24` (gold) | `#c8a84b` (gold) |
| Border | `#e5e7eb` | `#3a3044` (dust) |

**Fonts:** Cinzel Decorative (headlines), Cormorant Garamond (body)  
**Tone:** Mystical, esoteric, ancient grimoire aesthetic  
**When:** Perfect for night mode + user interested in design/UX depth

---

#### 🎸 **Rock Mag**
| Element | Light (Current) | Rock Mag |
|---------|---------|---------|
| Background | `#ffffff` | `#e8e0d0` (newsprint) |
| Surface | `#f3f4f6` | `#f5f0e8` (cream) |
| Primary (accent) | `#3b82f6` | `#c4420a` (rust) |
| Secondary | `#8b5cf6` | `#8b2020` (faded-red) |
| Text primary | `#1f2937` | `#1a1410` (ink) |
| Text secondary | `#6b7280` | `#4a4a4a` (slate) |
| Accent (highlights) | `#fbbf24` | `#d4a017` (goldenrod) |
| Border | `#e5e7eb` | `#2c2416` (smudge) |

**Fonts:** Playfair Display (headlines), Courier Prime (body/monospace)  
**Tone:** Vintage magazine (1970s Creem/Rolling Stone), scotch tape + newsprint texture  
**When:** User wants warm, retro feel; editorial/content-focused

---

#### 💀 **Gonzo Dark**
| Element | Light (Current) | Gonzo Dark |
|---------|---------|---------|
| Background | `#ffffff` | `#0a0804` (void) |
| Surface | `#f3f4f6` | `#111009` (pitch) |
| Primary (accent) | `#3b82f6` | `#b8e04a` (acid green) |
| Secondary | `#8b5cf6` | `#e8620a` (ember orange) |
| Text primary | `#1f2937` | `#e2d5be` (bone) |
| Text secondary | `#6b7280` | `#c8b89a` (parchment) |
| Accent (highlights) | `#fbbf24` | `#cc2200` (blood red) |
| Border | `#e5e7eb` | `#3d3428` (ink-brown) |

**Fonts:** Abril Fatface (headlines), Courier Prime (body)  
**Tone:** Chaotic, Fear & Loathing–inspired; scanlines + splatter effects  
**When:** User wants energy, attitude, hacker/gonzo aesthetic

---

### Implementation Roadmap (1 week)

#### Step 1: Create Theme Files (1 day)
- [ ] `web/src/themes/occult-dark.css` with `[data-theme="occult-dark"]` block
- [ ] `web/src/themes/rock-mag.css` with `[data-theme="rock-mag"]` block
- [ ] `web/src/themes/gonzo-dark.css` with `[data-theme="gonzo-dark"]` block
- Each file: ~50 lines defining CSS variable overrides

**Template Example:**
```css
/* web/src/themes/occult-dark.css */
[data-theme="occult-dark"] {
  --color-background: #020103;
  --color-surface: #08050a;
  --color-primary: #c41e1e;
  --color-on-surface: #ead0cc;
  --color-border: #3a3044;
  /* ... etc */
}
```

#### Step 2: Update Theme Registry (1 day)
- [ ] Import all three new CSS files in `web/src/themes/index.ts` or `web/src/index.css`
- [ ] Add to `THEMES` array:
```typescript
export const THEMES = [
  { id: 'light', label: 'Light', preview: ['#ffffff', '#f3f4f6', '#3b82f6'] },
  { id: 'dark', label: 'Dark', preview: ['#1f2937', '#111827', '#8b5cf6'] },
  { id: 'occult-dark', label: 'Occult Dark', preview: ['#020103', '#08050a', '#c41e1e'] },
  { id: 'rock-mag', label: 'Rock Mag', preview: ['#e8e0d0', '#f5f0e8', '#c4420a'] },
  { id: 'gonzo-dark', label: 'Gonzo Dark', preview: ['#0a0804', '#111009', '#b8e04a'] },
];
```

#### Step 3: Test & Polish (3 days)
- [ ] Test each theme across all views:
  - Chat (message contrast, avatar visibility)
  - Settings (form inputs, sliders)
  - Admin panels (tables, charts)
  - Command palette, toast notifications
- [ ] Verify color contrast (WCAG AA minimum 4.5:1 for text)
- [ ] Test on mobile (responsive theme application)
- [ ] Add subtle animations (optional: fade-in on theme switch)

#### Step 4: Update Settings UI (1 day)
- [ ] Appearance card already supports dynamic theme count
- [ ] Add theme descriptions in hover tooltip:
  - "Occult Dark: Mystical, esoteric aesthetic"
  - "Rock Mag: Vintage 1970s magazine vibes"
  - "Gonzo Dark: Chaotic, high-energy Feel & Loathing style"

#### Step 5: Documentation (1 day)
- [ ] Update CLAUDE.md Theme System section with new theme list
- [ ] Add to README: "Choose from 5 themes: Light, Dark, Occult Dark, Rock Mag, Gonzo Dark"
- [ ] (Optional) Create theme showcase page (`/themes-demo`) showing all skins side-by-side

---

## 📊 FINAL ROADMAP: Integration + Themes

### This Week (Apr 25–May 1)
- [ ] **Web UI parity validation** → identify model/workspace state sync issues
- [ ] **Theme skin implementation** → Occult, Rock Mag, Gonzo added to Settings
- [ ] **Cloud-local router prototype** → Phase 1 foundation (testing locally only)

### Next 2 Weeks (May 2–15)
- [ ] **Parity fixes** → model inventory + workspace sync live across launcher/web/API
- [ ] **Router integration** → Phase 2 wire into chat with user preference setting
- [ ] **Metrics dashboard** → Phase 3 expose routing decisions

### Month of May (May 16–31)
- [ ] **Agent spawning** → Phase 4 for complex tasks
- [ ] **FR-C tranches** → FR-C4–C10 cleanup + freeze-readiness validation
- [ ] **Performance profiling** → ensure cloud-local switching doesn't add overhead

### June (June 1–12)
- [ ] **Final freeze-readiness audit** → all P6 gates pass
- [ ] **Cost optimizer** → Phase 5 (stretch goal)
- [ ] **Release candidate** → June 12 deadline

---

## 🎓 Key Decisions

### 1. **Cloud-Local Routing: Intent-Based vs. Heuristic**
- **Decision:** Start with heuristic (token count + user preference), upgrade to ML after Phase 3
- **Rationale:** Heuristic launches faster; ML requires data collection first
- **Flexibility:** Swappable router interface allows easy upgrade

### 2. **Theme Skins: Cosmetic-Only or Semantic?**
- **Decision:** Cosmetic only (no functional changes, no accessibility impact)
- **Rationale:** Reduces maintenance burden; keeps accessibility uniform
- **Implementation:** CSS variable overrides only; no HTML changes

### 3. **Fallback Chain: Hard-Coded or User-Defined?**
- **Decision:** Smart defaults (router picks best chain) + user can override in Settings
- **Rationale:** Most users don't want to configure; power users can tune
- **Scaling:** Simple UI: sliders for "Speed ← → Quality ← → Cost"

### 4. **P6 vs. Cloud-Local Integration**
- **Decision:** P6 gates (parity, stability) complete by June 12; cloud-local routing by June 30
- **Rationale:** P6 is blocker; routing is enhancement
- **Packaging:** Both ship together in July release

---

## ✅ Success Criteria

### For Cloud-Local Integration
- [ ] Router selects appropriate provider (local, cloud-tier1, cloud-tier2)
- [ ] Fallback chain works: primary fails → secondary invoked
- [ ] Latency <100ms overhead from routing (vs. direct call)
- [ ] Cost tracking accurate within 1%
- [ ] User can switch preferences in Settings (speed/cost/quality)

### For Theme Skins
- [ ] All 5 themes render correctly across all views
- [ ] Color contrast passes WCAG AA (4.5:1 text)
- [ ] Theme persists across session reload
- [ ] Mobile responsive (no broken layout on narrow screens)
- [ ] Smooth fade-in on theme switch (optional polish)

### For P6 Gates
- [ ] Web UI model list matches launcher (same Ollama + cloud models)
- [ ] Workspace state syncs: create in web → visible in launcher (and vice versa)
- [ ] Chat stability under provider switch: no dropouts, queue + retry
- [ ] Statistics accurate: tool counts, model availability, latency metrics

---

## 📌 Next Immediate Actions

**This session:**
1. Review this roadmap with stakeholder(s)
2. Confirm priority: parity validation vs. router implementation
3. Assign effort: 1–2 developers needed for full scope

**This week:**
1. **Validation sprint:** Audit model/workspace state across launcher/web/API
2. **Theme preparation:** Extract color palettes from HTML files → CSS variable definitions
3. **Router sketch:** Draft `providers/`, `TaskRouter`, `RouteChain` class structures

**Next week:**
1. **Parity fixes:** Implement shared state contracts
2. **Theme release:** Occult, Rock Mag, Gonzo added to Settings
3. **Router Phase 1:** Foundation tests passing locally

---

**End of assessment. Ready to dive into any section with code or design work.**
