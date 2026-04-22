# Quarantine Directory

**Last update:** Removed 2026-04-22  
**Previous wave:** `.quarantine/2026-04-22_quarantine_wave_01/` (20,200 files, 2.9GB, deleted)

---

## Purpose

The `.quarantine/` directory is used to stage post-audit snapshots of the working tree for analysis, cleanup verification, and optional rollback during refactoring passes.

**When created:** After major audits or architectural evaluations  
**How long kept:** Usually 1–2 weeks; deleted once analysis is complete  
**Impact:** Does NOT go into git; is .gitignored; safe to delete without affecting source

---

## Quarantine Wave 01 (2026-04-22) — REMOVED

**Creation reason:** Post-evaluation snapshot after comprehensive repo audit

**Contents:** Full working tree split into logical areas for:
- Code archaeology (which files are truly active?)
- Dead-code identification (which modules can be removed?)
- Architecture validation (which seams are stable?)
- Freeze-readiness analysis (which modules are hotspots?)

**Analysis results:** No critical issues found. Repo is healthy. Voice system was genuinely broken (files removed separately). Quarantine wave no longer needed.

**Removal decision:** Deleted 2026-04-22 after:
1. Comprehensive evaluation completed
2. CLAUDE.md and EVALUATION_REPO_VS_ROADMAP_2026-04-22.md documented findings
3. All actionable items prioritized in memory
4. Release-check validated (all 8 gates passing)

**Retention decision:** No quarantine needed if next major checkpoint is clean. Recreate only if:
- Major refactoring pass occurs
- Significant code removal planned
- Need rollback safety during large changes

---

## If You See This Directory Later

**You are safe to:**
- Delete any `.quarantine/` directory without losing source code
- Ignore quarantine files in git status (they're .gitignored)
- Treat quarantine as temporary analysis staging, not production

**You should NOT:**
- Restore quarantine files to main codebase without explicit intent
- Treat quarantine contents as authoritative (snapshot may be stale)
- Assume anything in quarantine is production code (it's historical/analytical)

---

## Related Documentation

- **Evaluation findings:** `EVALUATION_REPO_VS_ROADMAP_2026-04-22.md` (why quarantine was created and deleted)
- **Architecture reference:** `CLAUDE.md` (stable truths extracted from quarantine analysis)
- **Memory system:** Check `guppy_freeze_readiness_program.md` for post-audit action plan

