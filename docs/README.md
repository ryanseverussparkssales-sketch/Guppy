# Docs Folder

This folder is the canonical source for active operational and product-facing reference docs.

## Canonical Docs

- `docs/PROJECT_BRIEF.md`
  - Current product surface, runtime scope, live features, and current gaps.
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

- `docs/M2_*.md`
  - Historical planning, launch, and design work for the M2 launcher push.
- `docs/MASTER_FIX_LIST.md`
  - Migration and cleanup execution ledger.
- `docs/LEGACY_QUARANTINE_PROTOCOL.md`
  - Legacy-surface quarantine history and removal notes.
- `docs/archive/`
  - Archived planning boards, handoff notes, and superseded references.
- `docs/generated/`
  - Generated follow-ups, audits, and one-off support material.

## Reading Order

1. Start with `docs/PROJECT_BRIEF.md` for current product state.
2. Use `documentation/README.md` for technical architecture and security truth.
3. Use `docs/API.md`, `docs/TROUBLESHOOTING.md`, `docs/VOICE.md`, and `docs/PACKAGING.md` for active operational work.
4. Treat M2, migration, generated, and archived docs as supporting history only.

## Canonicality Rule

If a historical or generated doc disagrees with `documentation/` or the canonical docs listed above, follow the canonical docs and live code.
