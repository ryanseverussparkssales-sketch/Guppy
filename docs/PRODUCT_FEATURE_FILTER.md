# Product Feature Filter

Last updated: 2026-04-18

Use this document to decide whether a feature should be kept, cut, deferred, or demoted.

This is intentionally strict. The goal is not to protect effort already spent. The goal is to protect product coherence.

## The First Question

Does this feature make Guppy better at being:

1. Personal.
2. Persistent.
3. Calm.
4. Useful with files.
5. Smooth in chat.

If the answer is "not really," it is probably not a priority.

## Keep

Keep a feature when it directly improves the daily workflow:

1. Makes Chat more useful or more trustworthy.
2. Makes Workspaces better at preserving purpose or continuity.
3. Makes Library better at finding, attaching, saving, or reusing files, notes, or artifacts.
4. Makes Settings safer or simpler without leaking complexity into the daily path.
5. Removes friction from startup, navigation, context recall, or tool use.

Examples to keep:

1. Reliable startup and warmup behavior.
2. Workspace switching and persistence.
3. File attach and reuse flows.
4. Pinned notes, saved artifacts, and recent file context.
5. Clear tool-availability awareness.
6. Better chat context carry-through.

## Cut

Cut a feature when it adds surface area without improving the core promise.

Cut or remove when it:

1. Duplicates another surface.
2. Exists mostly because it is technically possible.
3. Adds visible complexity to the daily path.
4. Exposes operator detail before the user needs it.
5. Makes Guppy feel more like a dashboard than an assistant.
6. Has weak adoption, weak trust, or no clear product story.

Examples likely to cut:

1. Duplicate status blocks across multiple surfaces.
2. Always-visible operational telemetry in Chat.
3. Extra navigation destinations that are really sub-pages of Settings.
4. Mode or route controls that are interesting internally but confusing to normal users.

## Demote

Demote a feature when it is useful but should not compete with the daily path.

Demote into `Settings`, drawers, or advanced sections when it:

1. Matters for setup or recovery, but not day-to-day work.
2. Is mostly for power users.
3. Is mostly for diagnosis, packaging, or runtime tuning.
4. Is important, but only after the user has a reason to look for it.

Examples to demote:

1. App Mgmt controls.
2. Runtime diagnostics.
3. Recovery flows.
4. Connector internals.
5. Operator logs.
6. Packaging and release evidence.

## Defer

Defer a feature when it is strategically attractive but would slow product coherence now.

Defer when it:

1. Depends on trust or smoothness that does not exist yet.
2. Requires broad new UI surface area.
3. Solves a future ambition before the current workflow feels good.
4. Makes Guppy larger before it becomes clearer.

Examples to defer:

1. Bigger ambient-assistant behavior.
2. Aggressive automation expansion.
3. New specialist surfaces.
4. Deep multi-provider or multi-agent product ideas that are not yet invisible to users.

## The Five-Gate Test

Before starting or keeping a feature, answer these five questions:

1. Does it improve `Chat`, `Workspaces`, `Library`, or `Settings` directly?
2. Does it make the daily workflow smoother for a normal user?
3. Will the value be obvious within one session?
4. Can it be explained in one sentence without internal jargon?
5. Can it land without making the main UI noisier?

Interpretation:

1. `5 yes` answers: keep and prioritize.
2. `4 yes` answers: probably keep.
3. `3 yes` answers: only keep if it removes real pain.
4. `2 or fewer yes` answers: cut, demote, or defer.

## The Red Flags

If a feature triggers any of these, pause:

1. "We already kind of have this somewhere else."
2. "This is mostly for future flexibility."
3. "Power users might want it visible."
4. "It is useful once you understand the rest of the product."
5. "We can explain it in the docs."
6. "It only feels good if everything else works perfectly."

Those usually mean the feature is too early, too loud, or too product-internal.

## Current Keep / Cut / Defer Bias

### Keep now

1. Chat smoothness.
2. Workspace continuity.
3. Library usefulness.
4. File attach and reuse.
5. Context persistence and recall.
6. Navigation clarity.
7. Startup reliability.
8. Calm UI cleanup.

### Demote now

1. App Mgmt prominence.
2. Runtime telemetry visibility.
3. Route and model operator detail on the daily path.
4. Recovery and diagnostics discoverability outside Settings.

### Defer now

1. Bigger "Jarvis" ambitions.
2. Broad automation expansion.
3. New major surfaces.
4. Fancy agent orchestration that is visible to users before the core workflow is smooth.

## Review Rule

When proposing a new feature or defending an old one, write the answer in this format:

1. `User value:`
2. `Primary surface affected:`
3. `Why now:`
4. `Keep / Cut / Demote / Defer:`
5. `Risk to calmness or clarity:`

If that write-up is weak, the feature should not lead the roadmap.
