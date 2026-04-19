# Business KPI Dashboard Brief — Library Feature

Last updated: April 18, 2026

**Audience:** Product, design, and non-technical stakeholders
**Review cadence:** Weekly for the first 8 weeks; biweekly thereafter once trends stabilize

---

## Product Goal

The Library feature gives users a persistent, workspace-scoped place to save files, notes, and reference documents so they can be reused directly in chat without hunting through secondary surfaces. The goal is to make working with Guppy feel like a continuous flow — where the context you care about is already there — rather than a series of disconnected sessions. Success means users are saving content to Library, pinning their key sources per workspace, and regularly pulling that context into their chat interactions.

---

## Top 5 Success Metrics

### 1. Library Attach Rate

**Plain English:** Out of every 10 chat messages a user sends, how many include at least one Library item as context?

A healthy attach rate means users have discovered that attaching Library items improves their answers and are doing it regularly. A low attach rate means the feature is present but not connected to the daily chat habit.

### 2. Default Source Pin Rate

**Plain English:** Out of all active workspaces in use, what fraction have a "default" Library source set that loads automatically?

When users pin a default, they are telling Guppy "this is the document I always want in context for this workspace." A growing pin rate means the feature feels trustworthy and worth personalizing. A flat or zero pin rate means users do not yet see the value or cannot find the affordance.

### 3. Context Reuse Depth

**Plain English:** When users do attach Library items, how many items do they typically attach in one session?

Depth above 1 means users are building multi-source context rather than attaching a single item as a one-off test. Depth that stays at exactly 1 may indicate the multi-item flow is unclear or untrusted.

### 4. Root Approval Rate

**Plain English:** When a user tries to add a folder as an approved Library source, how often does the save succeed on the first try?

A high approval rate means the root-selection experience is clear and the validation rules are not surprising users. A high rejection rate usually points to confusing error messages, path-picker friction, or permissions issues that need fixing.

### 5. Workspace Default Persistence

**Plain English:** When a user switches to a workspace that has a default Library source set, does that default actually show up in context automatically?

This is a trust metric. If the default disappears after a restart or workspace switch, users will stop setting defaults because they cannot rely on them. Near-100 % persistence is the bar.

---

## Current Baseline

Library shipped as a live feature in the current M2 window (active April 15, 2026). There is no historical usage data. All metrics start from zero on or after April 18, 2026, when instrumentation is activated.

| Metric | Baseline (April 18, 2026) |
|---|---|
| Library Attach Rate | 0 % (no data) |
| Default Source Pin Rate | 0 workspaces pinned |
| Context Reuse Depth | N/A |
| Root Approval Rate | N/A |
| Workspace Default Persistence | N/A |

---

## 30 / 60 / 90-Day Targets

| Metric | 30-Day Target (May 18) | 60-Day Target (June 17) | 90-Day Target (July 17) |
|---|---|---|---|
| Library Attach Rate | ≥ 15 % of chat sends include a Library item | ≥ 30 % | ≥ 40 % |
| Default Source Pin Rate | ≥ 1 workspace per active user has a default pinned | ≥ 50 % of workspaces that have Library content | ≥ 70 % |
| Context Reuse Depth | Average ≥ 1.1 items per attached send | Average ≥ 1.3 | Average ≥ 1.5 |
| Root Approval Rate | ≥ 80 % of root-save attempts succeed | ≥ 90 % | ≥ 95 % |
| Workspace Default Persistence | ≥ 90 % of switches restore a pinned default correctly | ≥ 95 % | ≥ 98 % |

*Targets are directional. Revisit at the 30-day review if the user base or usage patterns differ from assumptions.*

---

## Risk Signals

The following patterns in the data indicate Library is not gaining adoption and should trigger a design or UX review:

| Pattern | What It Likely Means |
|---|---|
| Attach Rate is flat at < 5 % after 30 days | Users do not know Library context can be sent to chat, or the attach affordance is invisible |
| Root Approval Rate is < 60 % | The root-add flow is confusing or surfacing technical errors users cannot recover from |
| Default Pin Rate is 0 after 30 days | The default-pin affordance is not discovered or the persistence is not trusted |
| Context Reuse Depth stays at exactly 1.0 | Users are trying the feature once as a test but not integrating it into a workflow |
| Workspace Default Persistence drops below 80 % | The `runtime/library_workspace_defaults.json` file is being cleared unexpectedly — likely a restart or cleanup issue |
| Large spike in `library.root_save_rejected` events | A platform or permissions change broke root validation silently |

---

## Review Cadence and Ownership

| Cadence | Activity | Owner |
|---|---|---|
| Weekly (weeks 1–8) | Review all 5 KPIs against targets; flag any risk signals; decide whether to run a design sprint | Product lead |
| Biweekly (week 9+) | Trend review; revisit 60/90-day targets if trajectory is clear | Product lead + design |
| Ad hoc | Any single metric drops > 15 % week-over-week | Whoever is on triage |

The raw JSONL data lives at `runtime/agent_performance.jsonl`. The KPI definitions and event schemas are in `docs/generated/KPI_INSTRUMENTATION_SPEC.md`.
