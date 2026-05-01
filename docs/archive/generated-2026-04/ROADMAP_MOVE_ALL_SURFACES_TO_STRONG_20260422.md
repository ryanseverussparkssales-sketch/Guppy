# Roadmap To Move Every Surface To Strong

Date: April 22, 2026

## Objective

Move every major Guppy product surface to a `strong` rating against the current product north star:

1. Personal
2. Persistent
3. Calm
4. Useful with files
5. Smooth in chat

This roadmap is based on:

- `docs/GUPPY_PRODUCT_NORTH_STAR.md`
- `docs/PRODUCT_FEATURE_FILTER.md`
- `docs/PROJECT_BRIEF.md`
- `docs/generated/CORE_INVENTORY_NORTH_STAR_AUDIT_20260422.md`

## Current Rating Snapshot

### Already Strong

1. Home Chat
2. Library
3. Settings
4. Tray / background runtime

### Not Yet Strong

1. Workspaces
2. Models
3. Tools
4. Memory / persistence payoff
5. Web backup UI

## Rules For This Roadmap

1. Do not reopen quarantined trees unless a specific visual reference or historical diff is needed.
2. Do not add new top-level product surfaces.
3. Keep Chat as the center of the product.
4. Demote operator detail instead of making Home louder.
5. Prefer finish-and-polish over feature expansion.

## Definition Of Strong

A surface is `strong` when:

1. Its purpose is obvious in one session.
2. It supports the daily workflow without adding visible clutter.
3. Its core flows are validated by release-check plus focused surface tests.
4. Its ownership boundaries are honest and easy to explain.
5. It no longer feels like a “mostly there” implementation lane.

## Execution Sequence

### Tranche S1: Continuity Spine

Goal:

- Make Guppy feel meaningfully persistent and easier to resume.

Focus:

1. Home continuity cues
2. Workspace switching and re-entry
3. Memory payoff in the visible user experience

Primary files:

- `compat_shims/launcher_ui/ui/launcher/views/assistant_view.py`
- `src/guppy/launcher_application/home_presenter.py`
- `compat_shims/launcher_ui/ui/launcher/views/instance_manager_view.py`
- `src/guppy/launcher_application/instance_manager_presenter.py`
- `src/guppy/memory/memory.py`
- `src/guppy/memory/memory_store.py`
- `src/guppy/memory/semantic.py`

Acceptance:

1. Returning to a workspace clearly shows what matters now.
2. Workspace purpose, recent context, and saved continuity are easier to resume from Home.
3. Memory is visible as user value, not just backend capability.
4. Home still feels calm.

Expected rating move:

- Workspaces: `good -> strong`
- Memory / persistence payoff: `implemented -> strong`
- Home Chat: `strong -> stronger but still calm`

### Tranche S2: File Flow Excellence

Goal:

- Make Library fast, calm, and obviously useful in the daily workflow.

Focus:

1. richer previews
2. cleaner metadata hierarchy
3. smoother attach / reuse / save loops

Primary files:

- `compat_shims/launcher_ui/ui/launcher/views/library_view.py`
- `compat_shims/launcher_ui/ui/launcher/views/library_media_panel.py`
- `src/guppy/launcher_application/library_presenter.py`

Acceptance:

1. The user can find, attach, and reuse a file or artifact without friction.
2. Saved notes and artifacts are easier to edit and reuse.
3. Media playback remains local and stable.
4. Library stays obviously subordinate to the chat-first workflow.

Expected rating move:

- Library: `strong -> strong and polished`

### Tranche S3: Tool Clarity And Plugin Truth

Goal:

- Make Tools feel dependable and explainable, not product-internal.

Focus:

1. clearer tool onboarding
2. better availability messaging
3. plugin/tool registry truth
4. current-vs-planned clarity

Primary files:

- `compat_shims/launcher_ui/ui/launcher/views/tools_view.py`
- `src/guppy/launcher_application/tool_action_registry.py`
- `src/guppy/launcher_application/launcher_tools_coordination.py`

Acceptance:

1. A normal user can tell what tools are available now.
2. Planned or partial tool lanes are labeled honestly.
3. Permissions and traces help when needed without dominating the page.
4. The plugin story is coherent enough to extend safely later.

Expected rating move:

- Tools: `solid foundation -> strong`

### Tranche S4: Model, Voice, And Local Runtime Confidence

Goal:

- Make the local-first runtime promise feel trustworthy and production-real.

Focus:

1. local runtime parity
2. provider honesty
3. voice lifecycle validation
4. planned-adapter clarity

Primary files:

- `compat_shims/launcher_ui/ui/launcher/views/models_hub_view.py`
- `compat_shims/launcher_ui/ui/launcher/views/models_view.py`
- `compat_shims/launcher_ui/ui/launcher/views/voices_view.py`
- `src/guppy/launcher_application/provider_registry.py`
- `src/guppy/workspace_governance/connector_service.py`

Acceptance:

1. Ollama, Lemonade, and LM Studio readiness are honest and understandable.
2. Voice routing and preview behavior are validated on real machines.
3. AnythingLLM and Hugging Face local remain clearly planned until real adapters land.
4. Model routing stays out of the Home daily path.

Expected rating move:

- Models: `useful and aligned -> strong`

### Tranche S5: Tray, Runtime, And Backup Web Alignment

Goal:

- Make all non-primary surfaces agree on one product truth.

Focus:

1. tray/runtime/API agreement
2. cleaner background-state handoff
3. web backup UI contract parity

Primary files:

- `src/guppy/hub/app.py`
- `src/guppy/daemon/daemon.py`
- `web/src/hooks/useAPI.ts`
- `web/src/hooks/useAppState.ts`
- `web/src/pages/Assistant.tsx`
- `web/src/pages/Workspace.tsx`
- `web/src/pages/Models.tsx`

Acceptance:

1. Tray, launcher, and backend agree on workspace/runtime status.
2. The web lane stays clearly secondary but accurate.
3. No stale API contract remains in backup UI behavior.

Expected rating move:

- Tray / background runtime: `strong -> strong and calmer`
- Web backup UI: `usable sidecar -> strong backup lane`

### Tranche S6: Calmness, Compactness, And Freeze Polish

Goal:

- Close the last “almost there” gaps and prepare the product for a calmer freeze posture.

Focus:

1. review-band module reduction where it improves readability
2. copy simplification
3. navigation and discoverability polish
4. repeated release-check and focused real-machine validation

Primary files:

- review-band launcher/view modules surfaced by line-cap guard
- packaging/readiness docs and runtime validation artifacts

Acceptance:

1. All major product surfaces feel calm and intentional.
2. Real-machine validation exists for the riskiest local-runtime and voice flows.
3. Release-check remains green throughout.
4. The product no longer feels like a shell plus separate implementation hubs.

## Surface Exit Criteria

### Home Chat

Strong when:

1. continuity is obvious on return
2. workspace context carries cleanly into conversation
3. the page stays calmer than competing local AI tools

### Workspaces

Strong when:

1. switching is easy
2. purpose is obvious
3. continuity survives return-to-work naturally

### Library

Strong when:

1. file reuse is fast
2. artifact and note handling feels durable
3. media handling is smooth and local

### Settings

Strong when:

1. credentials and recovery are easy to reason about
2. diagnostics are clear without being noisy
3. advanced controls stay demoted

### Models

Strong when:

1. local runtime truth is honest
2. voice + model lanes work together clearly
3. provider differences do not confuse the daily path

### Tools

Strong when:

1. available tools are obvious
2. plugin/tool growth has a clear contract
3. traces and permissions support trust rather than clutter

### Memory

Strong when:

1. users can feel persistence
2. recall improves work without re-explaining
3. continuity shows up in normal chat flow

### Tray / Runtime

Strong when:

1. background behavior is dependable
2. launcher/tray/runtime disagreement is rare and easy to diagnose
3. it helps without demanding attention

### Web Backup UI

Strong when:

1. it mirrors the live backend correctly
2. it is useful as fallback
3. it does not compete with the desktop product

## Highest-Value Order

If we only do the most important work first, the order should be:

1. S1 Continuity Spine
2. S3 Tool Clarity And Plugin Truth
3. S4 Model, Voice, And Local Runtime Confidence
4. S5 Tray, Runtime, And Backup Web Alignment
5. S2 File Flow Excellence
6. S6 Calmness, Compactness, And Freeze Polish

Reason:

- Continuity is the biggest remaining gap between “capable” and “strong”
- Tool/runtime truth is the biggest remaining trust gap
- Library is already strong enough that its work is polish, not rescue

## What This Roadmap Explicitly Avoids

1. reopening `splits/`
2. reintroducing archived or duplicate UI shells
3. adding new primary surfaces
4. broad visible automation expansion
5. reviving dashboard-heavy patterns that fight the north star

## Program Artifact

This roadmap should be treated as the current “move everything to strong” execution reference until the next audit refresh.
