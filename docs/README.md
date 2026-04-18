# Docs Folder

This folder is the canonical source for active operational and product-facing reference docs.

## Canonical Docs

- `docs/PROJECT_BRIEF.md`
  - Single active status, roadmap, checkpoint, and handoff document.
- `docs/GUPPY_PRODUCT_NORTH_STAR.md`
  - Product north star, scope boundary, and “what Guppy is / is not” definition.
- `docs/PRODUCT_FEATURE_FILTER.md`
  - Ruthless keep/cut/demote/defer filter for roadmap and feature decisions.
- `docs/API.md`
  - Active API surface, instance governance payload shape, and canonical implementation ownership.
- `docs/TROUBLESHOOTING.md`
  - Active operator troubleshooting steps, including workspace governance and Windows ops actions.
- `docs/VOICE.md`
  - Current voice implementation notes and runtime guidance.
- `docs/PACKAGING.md`
  - Current build and packaging guidance.
- `documentation/README.md`
  - Canonical technical architecture, security, and truth-audit index.

## Historical Or Planning Docs

These files remain useful for context, but they are not the canonical source of truth for current behavior unless they are explicitly linked from an active canonical doc.

- `docs/archive/planning-history/m2/`
  - Archived planning, launch, and design work for the M2 launcher push.
- `docs/MASTER_FIX_LIST.md`
  - Migration and cleanup execution ledger.
- `docs/LEGACY_QUARANTINE_PROTOCOL.md`
  - Legacy-surface quarantine history and removal notes.
- `docs/archive/`
  - Archived planning boards, handoff notes, and superseded references.
- `docs/generated/`
  - Generated follow-ups, audits, and one-off support material.

## Reading Order

1. Start with `docs/PROJECT_BRIEF.md` for current product state, active roadmap, and handoff notes.
2. Read `docs/GUPPY_PRODUCT_NORTH_STAR.md` and `docs/PRODUCT_FEATURE_FILTER.md` before proposing major product or UI scope.
3. Use `documentation/README.md` for technical architecture and security truth.
4. Use `docs/API.md`, `docs/TROUBLESHOOTING.md`, `docs/VOICE.md`, and `docs/PACKAGING.md` for active operational work.
4. Treat archived M2, migration, generated, and other archive docs as supporting history only.

## Canonicality Rule

If a historical or generated doc disagrees with `documentation/` or the canonical docs listed above, follow the canonical docs and live code.
