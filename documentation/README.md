# Documentation Folder

This folder is the canonical technical documentation source.

## Files

- `documentation/ARCHITECTURE.md`
  - Current architecture, runtime ownership, and component boundaries
- `documentation/SECURITY.md`
  - Auth, secrets, repair-token, request correlation, and test coverage
- `documentation/TRUTH_AUDIT.md`
  - Truth check of legacy docs against live code and canonical replacements

## Canonicality

- If a legacy markdown file disagrees with this folder, treat this folder as source of truth.
- Legacy files remain for historical context and should be migrated gradually.
- Canonical module paths now live under `src/guppy/`; root Python files are compatibility shims unless explicitly called out otherwise.
