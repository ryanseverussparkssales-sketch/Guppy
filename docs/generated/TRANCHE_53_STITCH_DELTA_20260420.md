# Tranche 53 Stitch And Inspiration Delta

Date: April 20, 2026

Scope:
- Repo-grounded implementation delta for `PL-C9`
- Compares current launcher to the active Guppy direction:
  - Google Stitch bundle guidance already captured in roadmap notes
  - Claude Desktop / ChatGPT Desktop calmness
  - Cursor / LM Studio desktop density and clarity

## Keep

1. Warm sand base surfaces and restrained blue/orange accent system in `ui/launcher/tokens.py`
2. Editorial serif limited to headings instead of whole-screen typography
3. Five-hub information architecture
4. Chat-first Home layout rather than operator-heavy dashboarding
5. Settings-owned credential and provider control plane

## Change

1. Chrome truthfulness
- The topbar should visibly show launcher readiness and startup state.
- Chat-context controls should open chat context, not a different destination.

2. Quiet hierarchy
- Topbar controls should feel like one coherent strip, with fewer ambiguous buttons competing equally.
- Model/state visibility should stay compact and obvious.

3. Responsive behavior
- Smaller widths need stricter hide/show rules and layout compression across all hubs.
- Card grids and topbar shells should not rely on generous desktop width.

4. Explanatory affordances
- Non-obvious controls need tooltips and clearer accessible descriptions.
- Remediation paths should point to one owner and one next step.

## Remove Or Avoid

1. Novelty chrome that competes with the chat surface
2. Over-bright gradients or theme flourishes that make the shell feel like a themed attraction
3. Multiple parallel "context" destinations with overlapping meaning
4. Status labels that imply success without actual readiness evidence

## Current repo-grounded deltas

1. Applied in this execution wave
- Added a visible topbar runtime/startup status chip.
- Corrected the topbar `CHAT` action to use chat-context drawer behavior.
- Fixed Home drawer toggling so it can actually open on Home.

2. Still open
- Full small-window sweep across Home, Models, Tools, Library, and Settings
- Tooltip completeness audit for all non-obvious controls
- Broader visual rhythm pass against Stitch spacing calmness
- Logo/art refinement audit against the downloaded Stitch identity direction

## Implementation guidance for next waves

1. Keep brand work subtle: sunset warmth and island flavor should read premium, not loud.
2. Prefer fewer, better controls over adding more chrome.
3. Every visible control should answer one of three questions quickly:
- What is this?
- What happens if I press it?
- Where do I go if it needs setup?
